import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "workflow-state.py"


class WorkflowStateTransitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state_path = Path(self.temp.name) / "state.json"

    def tearDown(self):
        self.temp.cleanup()

    def write_state(self, **values):
        state = {"RUN_ID": "run-1", "STATE": "NEW", "ATTEMPT_COUNT": 0}
        state.update(values)
        self.state_path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")

    def transition(self, event, *extra):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "transition", "--state", str(self.state_path), "--event", event, *extra],
            text=True,
            capture_output=True,
        )

    def test_canonical_transition_routes(self):
        cases = [
            ("NEW", "START", {}, "EXPLORING"),
            ("AWAITING_EXPLORE_APPROVAL", "REJECT", {}, "CANCELLED"),
            ("REVIEWING_PROPOSAL", "FAIL", {"ATTEMPT_COUNT": 0}, "REVISING_PROPOSAL"),
            ("REVIEWING_PROPOSAL", "FAIL", {"ATTEMPT_COUNT": 2}, "NEEDS_HUMAN"),
            ("AUDITING", "PASS", {}, "READY_TO_PUBLISH"),
            ("AUDITING", "PASS", {"PUBLISH_AUTHORIZED": True}, "PUBLISHING"),
            ("BLOCKED", "RESOLVED", {"RESUME_STATE": "AUDITING"}, "AUDITING"),
        ]
        for state, event, extra, expected in cases:
            with self.subTest(state=state, event=event):
                self.write_state(STATE=state, **extra)
                if state == "BLOCKED":
                    evidence = Path(self.temp.name) / "resolution.json"
                    evidence.write_text("resolved", encoding="utf-8")
                    result = self.transition(event, "--evidence", str(evidence))
                else:
                    result = self.transition(event)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(self.state_path.read_text(encoding="utf-8"))["STATE"], expected)

    def test_unknown_event_preserves_state_bytes(self):
        self.write_state(STATE="EXPLORING")
        before = self.state_path.read_bytes()
        result = self.transition("UNKNOWN")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.state_path.read_bytes(), before)


class WorkflowStateHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state_path = Path(self.temp.name) / "state.json"
        self.handoff_path = Path(self.temp.name) / "handoff.json"

    def tearDown(self):
        self.temp.cleanup()

    def write_state(self, state, attempt="attempt-current"):
        self.state_path.write_text(
            json.dumps({"RUN_ID": "run-1", "STATE": state, "ATTEMPT_ID": attempt}),
            encoding="utf-8",
        )

    def payload(self, **overrides):
        value = {
            "RUN_ID": "run-1", "ATTEMPT_ID": "attempt-current", "STATUS": "PASS",
            "CHANGE": None, "REQUEST_ARTIFACT": "request.md", "APPROVAL_ARTIFACT": None,
            "SUMMARY": "summary", "EVIDENCE": [], "BLOCKERS": [], "ARTIFACTS": [],
            "PROPOSAL_DIGEST": None, "PROGRESS_DIGEST": None, "BASE_SHA": None,
            "HEAD_SHA": None, "PUBLISH_STEP_RECEIPTS": [], "NEXT_STATE": "AWAITING_EXPLORE_APPROVAL",
            "OWNER": "Explore / Proposal",
        }
        value.update(overrides)
        self.handoff_path.write_text(json.dumps(value), encoding="utf-8")
        return value

    def run_command(self, command, event="PASS"):
        return subprocess.run(
            [sys.executable, str(SCRIPT), command, "--state", str(self.state_path),
             "--handoff", str(self.handoff_path), "--event", event],
            text=True,
            capture_output=True,
        )

    def test_accepts_valid_pre_change_and_post_apply_handoffs(self):
        self.write_state("EXPLORING")
        self.payload()
        result = self.run_command("validate-handoff")
        self.assertEqual(result.returncode, 0, result.stderr)

        self.write_state("APPLYING")
        self.payload(
            OWNER="Apply Executor", CHANGE="sample-change", PROPOSAL_DIGEST="proposal",
            PROGRESS_DIGEST="progress", BASE_SHA="base", HEAD_SHA="head",
            APPROVAL_ARTIFACT="approval.json",
            NEXT_STATE="AUDITING",
        )
        result = self.run_command("validate-handoff")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejected_handoffs_leave_state_unchanged(self):
        cases = [
            {"RUN_ID": "other"},
            {"ATTEMPT_ID": "stale"},
            {"OWNER": "Apply Executor"},
            {"NEXT_STATE": "APPLYING"},
            {"STATUS": "INVALID"},
        ]
        for overrides in cases:
            with self.subTest(overrides=overrides):
                self.write_state("EXPLORING")
                self.payload(**overrides)
                before = self.state_path.read_bytes()
                result = self.run_command("transition")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.state_path.read_bytes(), before)

        self.write_state("APPLYING")
        self.payload(
            OWNER="Apply Executor", CHANGE="sample-change", PROPOSAL_DIGEST="proposal",
            PROGRESS_DIGEST="progress", BASE_SHA=None, HEAD_SHA="head",
            APPROVAL_ARTIFACT="approval.json", APPROVAL_DIGEST="approval",
            NEXT_STATE="AUDITING",
        )
        before = self.state_path.read_bytes()
        result = self.run_command("transition")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_transition_persists_only_a_valid_handoff(self):
        self.write_state("EXPLORING")
        self.payload()
        result = self.run_command("transition")
        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["STATE"], "AWAITING_EXPLORE_APPROVAL")
        self.assertEqual(len(state["HANDOFFS"]), 1)


class WorkflowStateDigestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.proposal = root / "proposal.md"
        self.design = root / "design.md"
        self.spec = root / "spec.md"
        self.tasks = root / "tasks.md"
        self.proposal.write_text("# Proposal\n", encoding="utf-8")
        self.design.write_text("# Design\n", encoding="utf-8")
        self.spec.write_text("# Spec\n", encoding="utf-8")
        self.tasks.write_text("- [ ] first task\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def digest(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "digest", "--input", str(self.proposal),
             "--input", str(self.design), "--input", str(self.spec), "--tasks", str(self.tasks)],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_checkbox_progress_does_not_change_proposal_digest(self):
        before = self.digest()
        self.tasks.write_text("- [x] first task\n", encoding="utf-8")
        after = self.digest()
        self.assertEqual(before["PROPOSAL_DIGEST"], after["PROPOSAL_DIGEST"])
        self.assertNotEqual(before["PROGRESS_DIGEST"], after["PROGRESS_DIGEST"])

    def test_task_text_and_design_change_proposal_digest(self):
        before = self.digest()
        self.tasks.write_text("- [ ] revised task\n", encoding="utf-8")
        self.assertNotEqual(before["PROPOSAL_DIGEST"], self.digest()["PROPOSAL_DIGEST"])
        self.tasks.write_text("- [ ] first task\n", encoding="utf-8")
        self.design.write_text("# Changed Design\n", encoding="utf-8")
        self.assertNotEqual(before["PROPOSAL_DIGEST"], self.digest()["PROPOSAL_DIGEST"])


class WorkflowStateInitApprovalAndReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / "project"
        self.project.mkdir()
        for command in (
            ["git", "init"],
            ["git", "config", "user.email", "test@example.com"],
            ["git", "config", "user.name", "Test User"],
            ["git", "remote", "add", "origin", "https://example.test/repo.git"],
        ):
            subprocess.run(command, cwd=self.project, check=True, capture_output=True)
        (self.project / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=self.project, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=self.project, check=True, capture_output=True)

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, *arguments):
        return subprocess.run([sys.executable, str(SCRIPT), *arguments], text=True, capture_output=True)

    def init(self):
        (self.project / "baseline.txt").write_text("preserve\n", encoding="utf-8")
        result = self.invoke("init", "--project", str(self.project), "--request", "Improve docs",
                             "--source", "https://example.test/request", "--publish")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout), result

    def test_init_captures_provenance_and_approval_binds_explore_result(self):
        state, _ = self.init()
        state_path = Path(state["STATE_PATH"])
        persisted = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["STATE"], "NEW")
        self.assertEqual(persisted["PROJECT_REALPATH"], str(self.project.resolve()))
        self.assertEqual(persisted["REMOTE_URL"], "https://example.test/repo.git")
        self.assertIn("baseline.txt", persisted["UNTRACKED_BASELINE"])
        self.assertTrue(Path(persisted["REQUEST_ARTIFACT"]).is_file())
        request = Path(persisted["REQUEST_ARTIFACT"]).read_text(encoding="utf-8")
        self.assertIn(str(self.project.resolve()), request)
        self.assertIn(persisted["BRANCH"], request)
        self.assertIn(persisted["REMOTE_URL"], request)

        self.assertEqual(self.invoke("transition", "--state", str(state_path), "--event", "START").returncode, 0)
        self.assertEqual(self.invoke("transition", "--state", str(state_path), "--event", "PASS").returncode, 0)
        explore = self.project / "explore.md"
        explore.write_text("Explore result\n", encoding="utf-8")
        result = self.invoke("approve", "--state", str(state_path), "--decision", "APPROVE",
                             "--explore-result", str(explore), "--publish-authorized")
        self.assertEqual(result.returncode, 0, result.stderr)
        approved = json.loads(state_path.read_text(encoding="utf-8"))
        approval = json.loads(Path(approved["APPROVAL_ARTIFACT"]).read_text(encoding="utf-8"))
        self.assertEqual(approval["DECISION"], "APPROVE")
        self.assertEqual(approval["PROJECT_REALPATH"], str(self.project.resolve()))
        self.assertTrue(approval["PUBLISH_AUTHORIZED"])
        self.assertIn("DECIDED_AT", approval)
        self.assertEqual(approved["EXPLORE_DIGEST"], approval["EXPLORE_DIGEST"])

    def test_publish_receipts_are_ordered_replayable_and_finish_at_complete(self):
        state_path = self.project / "state.json"
        state_path.write_text(json.dumps({"RUN_ID": "run-1", "STATE": "PUBLISHING"}), encoding="utf-8")
        first = self.project / "preflight.json"
        first.write_text("preflight", encoding="utf-8")
        skipped = self.invoke("publish-receipt", "--state", str(state_path), "--step", "ARCHIVE",
                              "--result-file", str(first))
        self.assertNotEqual(skipped.returncode, 0)
        self.assertEqual(json.loads(state_path.read_text(encoding="utf-8"))["STATE"], "PUBLISHING")

        steps = ["PREFLIGHT", "ARCHIVE", "VALIDATE", "FINAL_COMMIT", "PUSH", "LINEAR_SYNC", "COMPLETE"]
        for step in steps:
            result_file = self.project / (step.lower() + ".json")
            result_file.write_text(step, encoding="utf-8")
            result = self.invoke("publish-receipt", "--state", str(state_path), "--step", step,
                                 "--result-file", str(result_file))
            self.assertEqual(result.returncode, 0, result.stderr)
            saved = json.loads(state_path.read_text(encoding="utf-8"))
            expected = "DONE" if step == "COMPLETE" else "PUBLISHING"
            self.assertEqual(saved["STATE"], expected)

        complete_file = self.project / "complete.json"
        replay = self.invoke("publish-receipt", "--state", str(state_path), "--step", "COMPLETE",
                             "--result-file", str(complete_file))
        self.assertEqual(replay.returncode, 0, replay.stderr)
        self.assertEqual(len(json.loads(state_path.read_text(encoding="utf-8"))["PUBLISH_STEP_RECEIPTS"]), 7)

class WorkflowStateFixRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state_path = self.root / "state.json"
        self.handoff_path = self.root / "handoff.json"

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, *arguments):
        return subprocess.run([sys.executable, str(SCRIPT), *arguments], text=True, capture_output=True)

    def write_state(self, **values):
        state = {"RUN_ID": "run-1", "STATE": "EXPLORING", "ATTEMPT_ID": "attempt-1"}
        state.update(values)
        self.state_path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")

    def handoff(self, **overrides):
        payload = {
            "RUN_ID": "run-1", "ATTEMPT_ID": "attempt-1", "STATUS": "PASS",
            "CHANGE": None, "REQUEST_ARTIFACT": "request.md", "APPROVAL_ARTIFACT": None,
            "SUMMARY": "summary", "EVIDENCE": [], "BLOCKERS": [], "ARTIFACTS": [],
            "PROPOSAL_DIGEST": None, "PROGRESS_DIGEST": None, "BASE_SHA": None,
            "HEAD_SHA": None, "PUBLISH_STEP_RECEIPTS": [], "NEXT_STATE": "AWAITING_EXPLORE_APPROVAL",
            "OWNER": "Explore / Proposal",
        }
        payload.update(overrides)
        self.handoff_path.write_text(json.dumps(payload), encoding="utf-8")

    def transition(self, event, handoff=True, *extra):
        arguments = ["transition", "--state", str(self.state_path), "--event", event, *extra]
        if handoff:
            arguments.extend(["--handoff", str(self.handoff_path)])
        return self.invoke(*arguments)

    def assert_json_error_and_unchanged(self, result, before):
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error", json.loads(result.stderr))
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_present_malformed_handoff_never_bypasses_validation(self):
        for payload in ({}, [], None):
            with self.subTest(payload=payload):
                self.write_state()
                self.handoff_path.write_text(json.dumps(payload), encoding="utf-8")
                before = self.state_path.read_bytes()
                self.assert_json_error_and_unchanged(self.transition("PASS"), before)

    def test_status_must_match_event_before_routing(self):
        self.write_state()
        self.handoff(STATUS="FAIL")
        before = self.state_path.read_bytes()
        self.assert_json_error_and_unchanged(self.transition("PASS"), before)

    def test_immutable_bindings_reject_mismatch_and_persist_to_state(self):
        self.write_state(STATE="APPLYING", CHANGE="change", PROPOSAL_DIGEST="proposal-a",
                         PROGRESS_DIGEST="progress-a", BASE_SHA="base-a", HEAD_SHA="head-a",
                         APPROVAL_ARTIFACT="approval.json", APPROVAL_DIGEST="approval-a")
        self.handoff(OWNER="Apply Executor", CHANGE="change", PROPOSAL_DIGEST="proposal-b",
                     PROGRESS_DIGEST="progress-a", BASE_SHA="base-a", HEAD_SHA="head-a",
                     APPROVAL_ARTIFACT="approval.json", NEXT_STATE="AUDITING")
        before = self.state_path.read_bytes()
        self.assert_json_error_and_unchanged(self.transition("PASS"), before)
        self.handoff(OWNER="Apply Executor", CHANGE="change", PROPOSAL_DIGEST="proposal-a",
                     PROGRESS_DIGEST="progress-a", BASE_SHA="base-a", HEAD_SHA="head-a",
                     APPROVAL_ARTIFACT="approval.json", NEXT_STATE="AUDITING")
        result = self.transition("PASS")
        self.assertEqual(result.returncode, 0, result.stderr)
        persisted = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["PROPOSAL_DIGEST"], "proposal-a")
        self.assertEqual(persisted["BASE_SHA"], "base-a")

    def test_blocked_recovery_requires_evidence_and_valid_resume_state(self):
        self.write_state(STATE="AUDITING")
        self.assertEqual(self.transition("BLOCKED", False).returncode, 0)
        self.assertEqual(json.loads(self.state_path.read_text(encoding="utf-8"))["RESUME_STATE"], "AUDITING")
        before = self.state_path.read_bytes()
        self.assert_json_error_and_unchanged(self.transition("RESOLVED", False), before)
        evidence = self.root / "resolution.json"
        evidence.write_text("resolved", encoding="utf-8")
        self.assertEqual(self.transition("RESOLVED", False, "--evidence", str(evidence)).returncode, 0)
        self.write_state(STATE="BLOCKED", RESUME_STATE="NOT_A_STATE")
        before = self.state_path.read_bytes()
        self.assert_json_error_and_unchanged(self.transition("RESOLVED", False, "--evidence", str(evidence)), before)

    def test_review_and_audit_failure_counts_are_separate(self):
        self.write_state(STATE="AUDITING", ATTEMPT_COUNT=2, PROPOSAL_FAILURE_COUNT=2, AUDIT_FAILURE_COUNT=0)
        result = self.transition("FAIL", False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.state_path.read_text(encoding="utf-8"))["STATE"], "FIXING_IMPLEMENTATION")

    def test_publishing_step_pass_only_completes_on_complete_step(self):
        self.write_state(STATE="PUBLISHING", CHANGE="change", PROPOSAL_DIGEST="proposal", PROGRESS_DIGEST="progress",
                         BASE_SHA="base", HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json", APPROVAL_DIGEST="approval",
                         PUBLISH_STEP_RECEIPTS=[])
        self.handoff(OWNER="Archivist / Publisher", CHANGE="change", PROPOSAL_DIGEST="proposal",
                     PROGRESS_DIGEST="progress", BASE_SHA="base", HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json",
                     PUBLISH_STEP="PREFLIGHT", ARCHIVE_DIGEST="archive", PUBLISH_STEP_RECEIPTS=[{"STEP": "PREFLIGHT"}],
                     NEXT_STATE="PUBLISHING")
        self.assertEqual(self.transition("STEP_PASS").returncode, 0)
        intermediate = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(intermediate["STATE"], "PUBLISHING")
        self.assertEqual(intermediate["PUBLISH_STEP_RECEIPTS"], [{"STEP": "PREFLIGHT"}])
        self.write_state(STATE="PUBLISHING", CHANGE="change", PROPOSAL_DIGEST="proposal", PROGRESS_DIGEST="progress",
                         BASE_SHA="base", HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json", APPROVAL_DIGEST="approval")
        self.handoff(OWNER="Archivist / Publisher", CHANGE="change", PROPOSAL_DIGEST="proposal",
                     PROGRESS_DIGEST="progress", BASE_SHA="base", HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json",
                     PUBLISH_STEP="COMPLETE", ARCHIVE_DIGEST="archive", PUBLISH_STEP_RECEIPTS=[{"STEP": "COMPLETE"}],
                     NEXT_STATE="DONE")
        self.assertEqual(self.transition("STEP_PASS").returncode, 0)
        self.assertEqual(json.loads(self.state_path.read_text(encoding="utf-8"))["STATE"], "DONE")

    def test_digest_normalizes_only_genuine_markers_and_input_order(self):
        proposal, design, tasks = self.root / "proposal.md", self.root / "design.md", self.root / "tasks.md"
        proposal.write_text("proposal\n", encoding="utf-8")
        design.write_text("design\n", encoding="utf-8")
        tasks.write_text("- [ ] task\nprose - [x] stays\n`- [x] inline`\n```\n- [x] code\n```\n", encoding="utf-8")
        command = ("digest", "--input", str(proposal), "--input", str(design), "--tasks", str(tasks))
        first = self.invoke(*command)
        self.assertEqual(first.returncode, 0, first.stderr)
        reversed_inputs = self.invoke("digest", "--input", str(design), "--input", str(proposal), "--tasks", str(tasks))
        self.assertEqual(json.loads(first.stdout), json.loads(reversed_inputs.stdout))
        tasks.write_text("- [x] task\nprose - [ ] stays\n`- [x] inline`\n```\n- [x] code\n```\n", encoding="utf-8")
        second = self.invoke(*command)
        self.assertNotEqual(json.loads(first.stdout)["PROPOSAL_DIGEST"], json.loads(second.stdout)["PROPOSAL_DIGEST"])

    def test_repeated_tasks_is_rejected_and_init_without_origin_succeeds(self):
        task_one, task_two, proposal = self.root / "one.md", self.root / "two.md", self.root / "proposal.md"
        task_one.write_text("- [ ] one\n", encoding="utf-8")
        task_two.write_text("- [ ] two\n", encoding="utf-8")
        proposal.write_text("proposal\n", encoding="utf-8")
        result = self.invoke("digest", "--input", str(proposal), "--tasks", str(task_one), "--tasks", str(task_two))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error", json.loads(result.stderr))
        project = self.root / "no-origin"
        project.mkdir()
        for command in (("git", "init"), ("git", "config", "user.email", "test@example.com"),
                        ("git", "config", "user.name", "Test User")):
            subprocess.run(command, cwd=project, check=True, capture_output=True)
        (project / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        subprocess.run(("git", "add", "tracked.txt"), cwd=project, check=True, capture_output=True)
        subprocess.run(("git", "commit", "-m", "initial"), cwd=project, check=True, capture_output=True)
        result = self.invoke("init", "--project", str(project), "--request", "request")
        self.assertEqual(result.returncode, 0, result.stderr)
        state_path = Path(json.loads(result.stdout)["STATE_PATH"])
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["REMOTE_URL"], "")
        receipt = self.root / "preflight.json"
        receipt.write_text("preflight", encoding="utf-8")
        state["STATE"] = "PUBLISHING"
        state_path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
        before = state_path.read_bytes()
        result = self.invoke("publish-receipt", "--state", str(state_path), "--step", "PREFLIGHT",
                             "--result-file", str(receipt))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(state_path.read_bytes(), before)

    def test_approve_rejects_tampered_review_bound_explore_result(self):
        explore, request = self.root / "explore.md", self.root / "request.md"
        explore.write_text("reviewed", encoding="utf-8")
        request.write_text("request", encoding="utf-8")
        self.write_state(STATE="AWAITING_EXPLORE_APPROVAL", REQUEST_ARTIFACT=str(request), PROJECT_REALPATH=str(self.root),
                         BRANCH="main", REMOTE_URL="", EXPLORE_ARTIFACT=str(explore),
                         EXPLORE_DIGEST=hashlib.sha256(explore.read_bytes()).hexdigest())
        explore.write_text("tampered", encoding="utf-8")
        before = self.state_path.read_bytes()
        result = self.invoke("approve", "--state", str(self.state_path), "--decision", "APPROVE", "--explore-result", str(explore))
        self.assert_json_error_and_unchanged(result, before)
        self.assertFalse((self.root / "approval.json").exists())

    def test_explore_handoff_persists_result_binding_for_approval(self):
        explore = self.root / "explore.md"
        explore.write_text("reviewed", encoding="utf-8")
        self.write_state()
        digest = hashlib.sha256(explore.read_bytes()).hexdigest()
        self.handoff(EXPLORE_ARTIFACT=str(explore), EXPLORE_DIGEST=digest)
        self.assertEqual(self.transition("PASS").returncode, 0)
        saved = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["EXPLORE_ARTIFACT"], str(explore))
        self.assertEqual(saved["EXPLORE_DIGEST"], digest)

    def test_uuid_attempt_and_inconsistent_receipt_preserve_state(self):
        self.write_state(STATE="NEW", ATTEMPT_ID="old-attempt")
        self.assertEqual(self.transition("START", False).returncode, 0)
        uuid.UUID(json.loads(self.state_path.read_text(encoding="utf-8"))["ATTEMPT_ID"])
        result_file = self.root / "result.json"
        result_file.write_text("same", encoding="utf-8")
        self.write_state(STATE="PUBLISHING", PUBLISH_STEP_RECEIPTS=[{
            "STEP": "PREFLIGHT", "RESULT_FILE": str(result_file.resolve()),
            "RESULT_DIGEST": hashlib.sha256(result_file.read_bytes()).hexdigest(),
        }])
        before = self.state_path.read_bytes()
        result = self.invoke("publish-receipt", "--state", str(self.state_path), "--step", "PREFLIGHT",
                             "--result-file", str(result_file), "--archive-digest", "different")
        self.assert_json_error_and_unchanged(result, before)


if __name__ == "__main__":
    unittest.main()
