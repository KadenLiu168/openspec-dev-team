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
PUBLISH_AUTHORIZATION_FIELDS = (
    "RUN_ID", "PROJECT_REALPATH", "BRANCH", "REMOTE_URL", "CHANGE",
    "APPROVAL_ARTIFACT", "APPROVAL_DIGEST", "PROPOSAL_DIGEST", "PROGRESS_DIGEST",
    "BASE_SHA", "HEAD_SHA", "UNTRACKED_BASELINE",
)


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
        authorized = {
            "PUBLISH_AUTHORIZED": True,
            "PROJECT_REALPATH": "/project", "BRANCH": "main", "REMOTE_URL": "origin",
            "CHANGE": "change", "APPROVAL_ARTIFACT": "approval.json", "APPROVAL_DIGEST": "approval",
            "PROPOSAL_DIGEST": "proposal", "PROGRESS_DIGEST": "progress",
            "BASE_SHA": "base", "HEAD_SHA": "head", "UNTRACKED_BASELINE": [],
        }
        authorized["PUBLISH_AUTHORIZATION"] = {
            field: ({"RUN_ID": "run-1", **authorized})[field]
            for field in PUBLISH_AUTHORIZATION_FIELDS
        }
        cases = [
            ("NEW", "START", {}, "EXPLORING"),
            ("AWAITING_EXPLORE_APPROVAL", "REJECT", {}, "CANCELLED"),
            ("REVIEWING_PROPOSAL", "FAIL", {"ATTEMPT_COUNT": 0}, "REVISING_PROPOSAL"),
            ("REVIEWING_PROPOSAL", "FAIL", {"ATTEMPT_COUNT": 2}, "NEEDS_HUMAN"),
            ("AUDITING", "PASS", {}, "READY_TO_PUBLISH"),
            ("AUDITING", "PASS", authorized, "PUBLISHING"),
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
        self.explore_path = Path(self.temp.name) / "explore.md"
        self.explore_path.write_text("explore", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def write_state(self, state, attempt="attempt-current"):
        self.state_path.write_text(
            json.dumps({"RUN_ID": "run-1", "STATE": state, "ATTEMPT_ID": attempt, "APPROVAL_DIGEST": "approval"}),
            encoding="utf-8",
        )

    def payload(self, **overrides):
        value = {
            "RUN_ID": "run-1", "ATTEMPT_ID": "attempt-current", "STATUS": "PASS",
            "CHANGE": None, "REQUEST_ARTIFACT": "request.md", "APPROVAL_ARTIFACT": None,
            "SUMMARY": "summary", "EVIDENCE": [], "BLOCKERS": [], "ARTIFACTS": [],
            "PROPOSAL_DIGEST": None, "PROGRESS_DIGEST": None, "BASE_SHA": None,
            "HEAD_SHA": None, "PUBLISH_STEP_RECEIPTS": [], "ARCHIVE_DIGEST": None,
            "NEXT_STATE": "AWAITING_EXPLORE_APPROVAL",
            "OWNER": "Explore / Proposal",
            "EXPLORE_ARTIFACT": str(self.explore_path),
            "EXPLORE_DIGEST": hashlib.sha256(self.explore_path.read_bytes()).hexdigest(),
        }
        value.update(overrides)
        value.setdefault("APPROVAL_DIGEST", "approval" if value.get("APPROVAL_ARTIFACT") else None)
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

    def test_accepts_post_apply_exact_contract_without_explore_fields(self):
        self.write_state("APPLYING")
        payload = {
            "RUN_ID": "run-1", "ATTEMPT_ID": "attempt-current", "STATUS": "PASS",
            "CHANGE": "sample-change", "REQUEST_ARTIFACT": "request.md", "APPROVAL_ARTIFACT": "approval.json",
            "APPROVAL_DIGEST": "approval",
            "SUMMARY": "summary", "EVIDENCE": [], "BLOCKERS": [], "ARTIFACTS": [],
            "PROPOSAL_DIGEST": "proposal", "PROGRESS_DIGEST": "progress", "BASE_SHA": "base",
            "HEAD_SHA": "head", "PUBLISH_STEP_RECEIPTS": [], "NEXT_STATE": "AUDITING", "OWNER": "Apply Executor",
        }
        self.handoff_path.write_text(json.dumps(payload), encoding="utf-8")
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
        self.assertEqual(before["PROGRESS_DIGEST"], hashlib.sha256(self.tasks.read_bytes()).hexdigest())
        self.tasks.write_text("- [x] first task\n", encoding="utf-8")
        after = self.digest()
        self.assertEqual(before["PROPOSAL_DIGEST"], after["PROPOSAL_DIGEST"])
        self.assertNotEqual(before["PROGRESS_DIGEST"], after["PROGRESS_DIGEST"])
        self.assertEqual(after["PROGRESS_DIGEST"], hashlib.sha256(self.tasks.read_bytes()).hexdigest())
        self.tasks.write_bytes(b"- [ ] caf\xc3\xa9")
        raw = self.digest()
        self.assertEqual(raw["PROGRESS_DIGEST"], hashlib.sha256(b"- [ ] caf\xc3\xa9").hexdigest())
        crlf_bytes = b"- [ ] task\r\nsecond line\r\n"
        self.tasks.write_bytes(crlf_bytes)
        crlf = self.digest()
        self.assertEqual(crlf["PROGRESS_DIGEST"], hashlib.sha256(crlf_bytes).hexdigest())

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

        explore = self.project / "explore.md"
        explore.write_text("Explore result\n", encoding="utf-8")
        self.assertEqual(self.invoke("transition", "--state", str(state_path), "--event", "START").returncode, 0)
        exploring = json.loads(state_path.read_text(encoding="utf-8"))
        exploring["EXPLORE_ARTIFACT"] = str(explore)
        exploring["EXPLORE_DIGEST"] = hashlib.sha256(explore.read_bytes()).hexdigest()
        state_path.write_text(json.dumps(exploring, sort_keys=True), encoding="utf-8")
        self.assertEqual(self.invoke("transition", "--state", str(state_path), "--event", "PASS").returncode, 0)
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

    def test_gate_authorization_is_completed_by_audit_before_direct_publishing(self):
        initialized, _ = self.init()
        state_path = Path(initialized["STATE_PATH"])
        handoff_path = self.project / "handoff.json"
        explore = self.project / "explore.md"
        explore.write_text("Approved direction\n", encoding="utf-8")

        def transition_handoff(owner, target, **overrides):
            state = json.loads(state_path.read_text(encoding="utf-8"))
            payload = {
                "RUN_ID": state["RUN_ID"], "ATTEMPT_ID": state["ATTEMPT_ID"], "STATUS": "PASS",
                "CHANGE": state.get("CHANGE"), "REQUEST_ARTIFACT": state["REQUEST_ARTIFACT"],
                "APPROVAL_ARTIFACT": state.get("APPROVAL_ARTIFACT"),
                "APPROVAL_DIGEST": state.get("APPROVAL_DIGEST"), "SUMMARY": "stage complete",
                "EVIDENCE": [], "BLOCKERS": [], "ARTIFACTS": [],
                "PROPOSAL_DIGEST": state.get("PROPOSAL_DIGEST"),
                "PROGRESS_DIGEST": state.get("PROGRESS_DIGEST"), "BASE_SHA": state.get("BASE_SHA"),
                "HEAD_SHA": state.get("HEAD_SHA"), "UNTRACKED_BASELINE": state["UNTRACKED_BASELINE"],
                "PUBLISH_STEP_RECEIPTS": [], "NEXT_STATE": target, "OWNER": owner,
            }
            payload.update(overrides)
            handoff_path.write_text(json.dumps(payload), encoding="utf-8")
            result = self.invoke("transition", "--state", str(state_path), "--event", "PASS",
                                 "--handoff", str(handoff_path))
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual(self.invoke("transition", "--state", str(state_path), "--event", "START").returncode, 0)
        transition_handoff(
            "Explore / Proposal", "AWAITING_EXPLORE_APPROVAL", CHANGE=None,
            PROPOSAL_DIGEST=None, PROGRESS_DIGEST=None,
            EXPLORE_ARTIFACT=str(explore), EXPLORE_DIGEST=hashlib.sha256(explore.read_bytes()).hexdigest(),
        )
        result = self.invoke("approve", "--state", str(state_path), "--decision", "APPROVE",
                             "--explore-result", str(explore), "--publish-authorized")
        self.assertEqual(result.returncode, 0, result.stderr)
        approved = json.loads(state_path.read_text(encoding="utf-8"))
        initial_authorization = approved["PUBLISH_AUTHORIZATION"]
        self.assertEqual(initial_authorization["UNTRACKED_BASELINE"], ["baseline.txt"])
        self.assertIsNone(initial_authorization["CHANGE"])
        self.assertEqual(initial_authorization["EVIDENCE"]["DIGEST"], approved["APPROVAL_DIGEST"])

        self.assertEqual(self.invoke("transition", "--state", str(state_path), "--event", "APPROVE").returncode, 0)
        transition_handoff(
            "Explore / Proposal", "REVIEWING_PROPOSAL", CHANGE="change",
            PROPOSAL_DIGEST="proposal", PROGRESS_DIGEST="tasks",
        )
        transition_handoff("Proposal Reviewer", "APPLYING")
        transition_handoff("Apply Executor", "AUDITING", HEAD_SHA="implemented")
        published = transition_handoff("Pre-Archive Auditor", "PUBLISHING")

        self.assertEqual(published["STATE"], "PUBLISHING")
        authorization = published["PUBLISH_AUTHORIZATION"]
        for field in PUBLISH_AUTHORIZATION_FIELDS:
            self.assertEqual(authorization[field], published[field])
        self.assertEqual(authorization["EVIDENCE"], initial_authorization["EVIDENCE"])
        self.assertEqual(authorization["AUTHORIZED_AT"], initial_authorization["AUTHORIZED_AT"])

    def test_publish_receipts_are_ordered_replayable_and_finish_at_complete(self):
        state_path = self.project / "state.json"
        handoff_path = self.project / "handoff.json"
        state = {
            "RUN_ID": "run-1", "STATE": "PUBLISHING", "ATTEMPT_ID": "attempt-1",
            "CHANGE": "change", "PROPOSAL_DIGEST": "proposal", "PROGRESS_DIGEST": "progress",
            "BASE_SHA": "base", "HEAD_SHA": "head", "APPROVAL_ARTIFACT": "approval.json",
            "APPROVAL_DIGEST": "approval",
            "REMOTE_URL": "https://example.test/repo.git", "PUBLISH_STEP_RECEIPTS": [],
        }
        state_path.write_text(json.dumps(state), encoding="utf-8")

        first = self.project / "archive.json"
        first.write_text("ARCHIVE", encoding="utf-8")
        skipped_receipt = {
            "STEP": "ARCHIVE", "RESULT_FILE": str(first.resolve()),
            "RESULT_DIGEST": hashlib.sha256(first.read_bytes()).hexdigest(),
            "RECORDED_AT": "2026-09-06T00:00:00+00:00",
            "INPUT_DIGESTS": {"PROPOSAL_DIGEST": "proposal", "PROGRESS_DIGEST": "progress"},
            "ARCHIVE_DIGEST": "archive",
        }
        skipped_handoff = {
            "RUN_ID": "run-1", "ATTEMPT_ID": "attempt-1", "STATUS": "PASS", "CHANGE": "change",
            "REQUEST_ARTIFACT": "request.md", "APPROVAL_ARTIFACT": "approval.json",
            "APPROVAL_DIGEST": "approval",
            "SUMMARY": "summary", "EVIDENCE": [], "BLOCKERS": [], "ARTIFACTS": [],
            "PROPOSAL_DIGEST": "proposal", "PROGRESS_DIGEST": "progress", "BASE_SHA": "base",
            "HEAD_SHA": "head", "PUBLISH_STEP_RECEIPTS": [skipped_receipt],
            "NEXT_STATE": "PUBLISHING", "OWNER": "Archivist / Publisher",
            "PUBLISH_STEP": "ARCHIVE", "ARCHIVE_DIGEST": "archive",
        }
        handoff_path.write_text(json.dumps(skipped_handoff), encoding="utf-8")
        before_skip = state_path.read_bytes()
        skipped = self.invoke(
            "publish-receipt", "--state", str(state_path), "--handoff", str(handoff_path),
            "--step", "ARCHIVE", "--result-file", str(first), "--archive-digest", "archive",
        )
        self.assertNotEqual(skipped.returncode, 0)
        self.assertEqual(state_path.read_bytes(), before_skip)

        steps = ["PREFLIGHT", "ARCHIVE", "VALIDATE", "FINAL_COMMIT", "PUSH", "LINEAR_SYNC", "COMPLETE"]
        receipts = []
        for index, step in enumerate(steps):
            result_file = self.project / (step.lower() + ".json")
            result_file.write_text(step, encoding="utf-8")
            saved = json.loads(state_path.read_text(encoding="utf-8"))
            receipt = {
                "STEP": step, "RESULT_FILE": str(result_file.resolve()),
                "RESULT_DIGEST": hashlib.sha256(result_file.read_bytes()).hexdigest(),
                "RECORDED_AT": "2026-09-06T00:00:%02d+00:00" % index,
                "INPUT_DIGESTS": {"PROPOSAL_DIGEST": "proposal", "PROGRESS_DIGEST": "progress"},
            }
            archive_digest = "archive" if index >= 1 else None
            final_sha = "final" if index >= 3 else None
            if archive_digest:
                receipt["ARCHIVE_DIGEST"] = archive_digest
            if final_sha:
                receipt["FINAL_SHA"] = final_sha
            handoff = {
                "RUN_ID": "run-1", "ATTEMPT_ID": saved["ATTEMPT_ID"], "STATUS": "PASS",
                "CHANGE": "change", "REQUEST_ARTIFACT": "request.md",
                "APPROVAL_ARTIFACT": "approval.json", "SUMMARY": "summary", "EVIDENCE": [],
                "APPROVAL_DIGEST": "approval",
                "BLOCKERS": [], "ARTIFACTS": [], "PROPOSAL_DIGEST": "proposal",
                "PROGRESS_DIGEST": "progress", "BASE_SHA": "base", "HEAD_SHA": "head",
                "PUBLISH_STEP_RECEIPTS": receipts + [receipt],
                "NEXT_STATE": "DONE" if step == "COMPLETE" else "PUBLISHING",
                "OWNER": "Archivist / Publisher", "PUBLISH_STEP": step,
                "ARCHIVE_DIGEST": archive_digest,
            }
            handoff_path.write_text(json.dumps(handoff), encoding="utf-8")
            validation = self.invoke(
                "validate-handoff", "--state", str(state_path), "--handoff", str(handoff_path),
                "--event", "STEP_PASS",
            )
            self.assertEqual(validation.returncode, 0, validation.stderr)
            arguments = [
                "publish-receipt", "--state", str(state_path), "--handoff", str(handoff_path),
                "--step", step, "--result-file", str(result_file),
            ]
            if archive_digest:
                arguments.extend(["--archive-digest", archive_digest])
            if final_sha:
                arguments.extend(["--final-sha", final_sha])
            result = self.invoke(*arguments)
            self.assertEqual(result.returncode, 0, result.stderr)
            recorded = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(recorded["STATE"], "PUBLISHING")
            self.assertEqual(recorded["PUBLISH_STEP_RECEIPTS"], receipts + [receipt])
            before_replay = state_path.read_bytes()
            replay = self.invoke(*arguments)
            self.assertEqual(replay.returncode, 0, replay.stderr)
            self.assertEqual(state_path.read_bytes(), before_replay)
            transition = self.invoke(
                "transition", "--state", str(state_path), "--handoff", str(handoff_path),
                "--event", "STEP_PASS",
            )
            self.assertEqual(transition.returncode, 0, transition.stderr)
            receipts.append(receipt)

        finished = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(finished["STATE"], "DONE")
        self.assertEqual(finished["PUBLISH_STEP_RECEIPTS"], receipts)

class WorkflowStateFixRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state_path = self.root / "state.json"
        self.handoff_path = self.root / "handoff.json"
        self.explore_path = self.root / "explore.md"
        self.explore_path.write_text("explore", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, *arguments):
        return subprocess.run([sys.executable, str(SCRIPT), *arguments], text=True, capture_output=True)

    def write_state(self, **values):
        state = {"RUN_ID": "run-1", "STATE": "EXPLORING", "ATTEMPT_ID": "attempt-1", "APPROVAL_DIGEST": "approval"}
        state.update(values)
        self.state_path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")

    def handoff(self, **overrides):
        payload = {
            "RUN_ID": "run-1", "ATTEMPT_ID": "attempt-1", "STATUS": "PASS",
            "CHANGE": None, "REQUEST_ARTIFACT": "request.md", "APPROVAL_ARTIFACT": None,
            "SUMMARY": "summary", "EVIDENCE": [], "BLOCKERS": [], "ARTIFACTS": [],
            "PROPOSAL_DIGEST": None, "PROGRESS_DIGEST": None, "BASE_SHA": None,
            "HEAD_SHA": None, "PUBLISH_STEP_RECEIPTS": [], "ARCHIVE_DIGEST": None,
            "NEXT_STATE": "AWAITING_EXPLORE_APPROVAL",
            "OWNER": "Explore / Proposal",
            "EXPLORE_ARTIFACT": str(self.explore_path),
            "EXPLORE_DIGEST": hashlib.sha256(self.explore_path.read_bytes()).hexdigest(),
        }
        payload.update(overrides)
        payload.setdefault("APPROVAL_DIGEST", "approval" if payload.get("APPROVAL_ARTIFACT") else None)
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

    def test_explore_pass_and_approval_require_accepted_binding(self):
        self.write_state()
        self.handoff(EXPLORE_ARTIFACT=None, EXPLORE_DIGEST=None)
        before = self.state_path.read_bytes()
        self.assert_json_error_and_unchanged(self.transition("PASS"), before)

        result = self.root / "result.md"
        request = self.root / "request.md"
        result.write_text("result", encoding="utf-8")
        request.write_text("request", encoding="utf-8")
        self.write_state(STATE="AWAITING_EXPLORE_APPROVAL", REQUEST_ARTIFACT=str(request),
                         PROJECT_REALPATH=str(self.root), BRANCH="main", REMOTE_URL="")
        before = self.state_path.read_bytes()
        approval = self.invoke("approve", "--state", str(self.state_path), "--decision", "APPROVE",
                               "--explore-result", str(result))
        self.assert_json_error_and_unchanged(approval, before)
        self.assertFalse((self.root / "approval.json").exists())

    def test_explore_blocked_handoff_does_not_require_result_binding(self):
        self.write_state()
        self.handoff(STATUS="BLOCKED", NEXT_STATE="BLOCKED", EXPLORE_ARTIFACT=None, EXPLORE_DIGEST=None)
        result = self.transition("BLOCKED")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.state_path.read_text(encoding="utf-8"))["STATE"], "BLOCKED")

    def test_publishing_unauthorized_preflight_blocked_needs_no_archive_receipt(self):
        self.write_state(
            STATE="PUBLISHING", CHANGE="change", PROPOSAL_DIGEST="proposal",
            PROGRESS_DIGEST="progress", BASE_SHA="base", HEAD_SHA="head",
            APPROVAL_ARTIFACT="approval.json", PUBLISH_STEP_RECEIPTS=[],
        )
        self.handoff(
            OWNER="Archivist / Publisher", STATUS="BLOCKED", CHANGE="change",
            PROPOSAL_DIGEST="proposal", PROGRESS_DIGEST="progress", BASE_SHA="base",
            HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json", PUBLISH_STEP="PREFLIGHT",
            ARCHIVE_DIGEST=None, PUBLISH_STEP_RECEIPTS=[], NEXT_STATE="BLOCKED",
            BLOCKERS=["publish authorization missing"],
        )
        result = self.transition("BLOCKED")
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["STATE"], "BLOCKED")
        self.assertEqual(saved["RESUME_STATE"], "PUBLISHING")
        self.assertEqual(saved["PUBLISH_STEP_RECEIPTS"], [])

        self.write_state(
            STATE="PUBLISHING", CHANGE="change", PROPOSAL_DIGEST="proposal",
            PROGRESS_DIGEST="progress", BASE_SHA="base", HEAD_SHA="head",
            APPROVAL_ARTIFACT="approval.json", PUBLISH_STEP_RECEIPTS=[],
        )
        for digest in ("archive", "__missing__"):
            with self.subTest(archive_digest=digest):
                self.handoff(
                    OWNER="Archivist / Publisher", STATUS="BLOCKED", CHANGE="change",
                    PROPOSAL_DIGEST="proposal", PROGRESS_DIGEST="progress", BASE_SHA="base",
                    HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json", PUBLISH_STEP="PREFLIGHT",
                    ARCHIVE_DIGEST=None, PUBLISH_STEP_RECEIPTS=[], NEXT_STATE="BLOCKED",
                    BLOCKERS=["publish authorization missing"],
                )
                payload = json.loads(self.handoff_path.read_text(encoding="utf-8"))
                if digest == "__missing__":
                    del payload["ARCHIVE_DIGEST"]
                else:
                    payload["ARCHIVE_DIGEST"] = digest
                self.handoff_path.write_text(json.dumps(payload), encoding="utf-8")
                before = self.state_path.read_bytes()
                result = self.transition("BLOCKED")
                self.assert_json_error_and_unchanged(result, before)
                self.assertIn("ARCHIVE_DIGEST=null", json.loads(result.stderr)["error"])

    def test_publishing_blocked_progress_requires_next_step_and_archive_binding(self):
        preflight = {"STEP": "PREFLIGHT"}
        archive = {"STEP": "ARCHIVE", "ARCHIVE_DIGEST": "archive"}
        cases = (
            ("post-archive missing digest", [preflight, archive], "VALIDATE", None, "missing ARCHIVE_DIGEST"),
            ("post-archive wrong digest", [preflight, archive], "VALIDATE", "other", "mismatched ARCHIVE_DIGEST"),
            ("post-archive claims preflight", [preflight, archive], "PREFLIGHT", "archive", "inconsistent PUBLISH_STEP"),
            ("post-archive claims complete", [preflight, archive], "COMPLETE", "archive", "inconsistent PUBLISH_STEP"),
        )
        for label, receipts, step, archive_digest, error in cases:
            with self.subTest(label=label):
                self.write_state(
                    STATE="PUBLISHING", CHANGE="change", PROPOSAL_DIGEST="proposal",
                    PROGRESS_DIGEST="progress", BASE_SHA="base", HEAD_SHA="head",
                    APPROVAL_ARTIFACT="approval.json", PUBLISH_STEP_RECEIPTS=receipts,
                )
                self.handoff(
                    OWNER="Archivist / Publisher", STATUS="BLOCKED", CHANGE="change",
                    PROPOSAL_DIGEST="proposal", PROGRESS_DIGEST="progress", BASE_SHA="base",
                    HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json", PUBLISH_STEP=step,
                    ARCHIVE_DIGEST=archive_digest, PUBLISH_STEP_RECEIPTS=receipts,
                    NEXT_STATE="BLOCKED", BLOCKERS=["blocked"],
                )
                before = self.state_path.read_bytes()
                result = self.transition("BLOCKED")
                self.assert_json_error_and_unchanged(result, before)
                self.assertIn(error, json.loads(result.stderr)["error"])

    def test_publishing_blocked_after_archive_accepts_bound_next_step(self):
        receipts = [
            {"STEP": "PREFLIGHT"},
            {"STEP": "ARCHIVE", "ARCHIVE_DIGEST": "archive"},
        ]
        self.write_state(
            STATE="PUBLISHING", CHANGE="change", PROPOSAL_DIGEST="proposal",
            PROGRESS_DIGEST="progress", BASE_SHA="base", HEAD_SHA="head",
            APPROVAL_ARTIFACT="approval.json", PUBLISH_STEP_RECEIPTS=receipts,
        )
        self.handoff(
            OWNER="Archivist / Publisher", STATUS="BLOCKED", CHANGE="change",
            PROPOSAL_DIGEST="proposal", PROGRESS_DIGEST="progress", BASE_SHA="base",
            HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json", PUBLISH_STEP="VALIDATE",
            ARCHIVE_DIGEST="archive", PUBLISH_STEP_RECEIPTS=receipts,
            NEXT_STATE="BLOCKED", BLOCKERS=["validation unavailable"],
        )
        result = self.transition("BLOCKED")
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["STATE"], "BLOCKED")
        self.assertEqual(saved["PUBLISH_STEP_RECEIPTS"], receipts)

    def test_publishing_success_still_rejects_missing_stage_requirements(self):
        base = {
            "STATE": "PUBLISHING", "CHANGE": "change", "PROPOSAL_DIGEST": "proposal",
            "PROGRESS_DIGEST": "progress", "BASE_SHA": "base", "HEAD_SHA": "head",
            "APPROVAL_ARTIFACT": "approval.json", "PUBLISH_STEP_RECEIPTS": [],
        }
        archive_prefix = [{"STEP": "PREFLIGHT"}]
        self.write_state(**base)
        self.handoff(
            OWNER="Archivist / Publisher", CHANGE="change", PROPOSAL_DIGEST="proposal",
            PROGRESS_DIGEST="progress", BASE_SHA="base", HEAD_SHA="head",
            APPROVAL_ARTIFACT="approval.json", PUBLISH_STEP="PREFLIGHT",
            ARCHIVE_DIGEST=None, PUBLISH_STEP_RECEIPTS=[], NEXT_STATE="PUBLISHING",
        )
        before = self.state_path.read_bytes()
        result = self.transition("STEP_PASS")
        self.assert_json_error_and_unchanged(result, before)
        self.assertIn("missing PUBLISH_STEP_RECEIPTS", json.loads(result.stderr)["error"])

        self.write_state(**{**base, "PUBLISH_STEP_RECEIPTS": archive_prefix})
        self.handoff(
            OWNER="Archivist / Publisher", CHANGE="change", PROPOSAL_DIGEST="proposal",
            PROGRESS_DIGEST="progress", BASE_SHA="base", HEAD_SHA="head",
            APPROVAL_ARTIFACT="approval.json", PUBLISH_STEP="ARCHIVE",
            ARCHIVE_DIGEST=None, PUBLISH_STEP_RECEIPTS=archive_prefix + [{"STEP": "ARCHIVE"}],
            NEXT_STATE="PUBLISHING",
        )
        before = self.state_path.read_bytes()
        result = self.transition("STEP_PASS")
        self.assert_json_error_and_unchanged(result, before)
        self.assertIn("missing ARCHIVE_DIGEST", json.loads(result.stderr)["error"])

    def test_audit_fail_handoff_uses_audit_counter_not_proposal_counter(self):
        self.write_state(STATE="AUDITING", ATTEMPT_COUNT=2, PROPOSAL_FAILURE_COUNT=2, AUDIT_FAILURE_COUNT=0,
                         CHANGE="change", PROPOSAL_DIGEST="proposal", PROGRESS_DIGEST="progress",
                         BASE_SHA="base", HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json")
        self.handoff(OWNER="Pre-Archive Auditor", STATUS="FAIL", CHANGE="change", PROPOSAL_DIGEST="proposal",
                     PROGRESS_DIGEST="progress", BASE_SHA="base", HEAD_SHA="head",
                     APPROVAL_ARTIFACT="approval.json", NEXT_STATE="FIXING_IMPLEMENTATION")
        result = self.transition("FAIL")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.state_path.read_text(encoding="utf-8"))["STATE"], "FIXING_IMPLEMENTATION")

    def test_immutable_bindings_reject_mismatch_and_persist_to_state(self):
        self.write_state(STATE="APPLYING", CHANGE="change", PROPOSAL_DIGEST="proposal-a",
                         PROGRESS_DIGEST="progress-a", BASE_SHA="base-a", HEAD_SHA="head-a",
                         APPROVAL_ARTIFACT="approval.json", APPROVAL_DIGEST="approval-a")
        self.handoff(OWNER="Apply Executor", CHANGE="change", PROPOSAL_DIGEST="proposal-b",
                     PROGRESS_DIGEST="progress-a", BASE_SHA="base-a", HEAD_SHA="head-a",
                     APPROVAL_ARTIFACT="approval.json", APPROVAL_DIGEST="approval-a", NEXT_STATE="AUDITING")
        before = self.state_path.read_bytes()
        self.assert_json_error_and_unchanged(self.transition("PASS"), before)
        self.handoff(OWNER="Apply Executor", CHANGE="change", PROPOSAL_DIGEST="proposal-a",
                     PROGRESS_DIGEST="progress-a", BASE_SHA="base-a", HEAD_SHA="head-a",
                     APPROVAL_ARTIFACT="approval.json", APPROVAL_DIGEST="approval-a", NEXT_STATE="AUDITING")
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
        complete_prefix = [{"STEP": step} for step in ("PREFLIGHT", "ARCHIVE", "VALIDATE", "FINAL_COMMIT", "PUSH", "LINEAR_SYNC")]
        self.write_state(STATE="PUBLISHING", CHANGE="change", PROPOSAL_DIGEST="proposal", PROGRESS_DIGEST="progress",
                         BASE_SHA="base", HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json", APPROVAL_DIGEST="approval",
                         PUBLISH_STEP_RECEIPTS=complete_prefix)
        self.handoff(OWNER="Archivist / Publisher", CHANGE="change", PROPOSAL_DIGEST="proposal",
                     PROGRESS_DIGEST="progress", BASE_SHA="base", HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json",
                     PUBLISH_STEP="COMPLETE", ARCHIVE_DIGEST="archive", PUBLISH_STEP_RECEIPTS=complete_prefix + [{"STEP": "COMPLETE"}],
                     NEXT_STATE="DONE")
        self.assertEqual(self.transition("STEP_PASS").returncode, 0)
        self.assertEqual(json.loads(self.state_path.read_text(encoding="utf-8"))["STATE"], "DONE")

    def test_step_pass_rejects_forged_completion_and_accepts_contiguous_completion(self):
        self.write_state(STATE="PUBLISHING", CHANGE="change", PROPOSAL_DIGEST="proposal", PROGRESS_DIGEST="progress",
                         BASE_SHA="base", HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json", PUBLISH_STEP_RECEIPTS=[])
        self.handoff(OWNER="Archivist / Publisher", CHANGE="change", PROPOSAL_DIGEST="proposal",
                     PROGRESS_DIGEST="progress", BASE_SHA="base", HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json",
                     PUBLISH_STEP="COMPLETE", ARCHIVE_DIGEST="archive", PUBLISH_STEP_RECEIPTS=[{"STEP": "COMPLETE"}],
                     NEXT_STATE="DONE")
        before = self.state_path.read_bytes()
        self.assert_json_error_and_unchanged(self.transition("STEP_PASS"), before)

        prefix = [{"STEP": step} for step in ("PREFLIGHT", "ARCHIVE", "VALIDATE", "FINAL_COMMIT", "PUSH", "LINEAR_SYNC")]
        self.write_state(STATE="PUBLISHING", CHANGE="change", PROPOSAL_DIGEST="proposal", PROGRESS_DIGEST="progress",
                         BASE_SHA="base", HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json", PUBLISH_STEP_RECEIPTS=prefix)
        self.handoff(OWNER="Archivist / Publisher", CHANGE="change", PROPOSAL_DIGEST="proposal",
                     PROGRESS_DIGEST="progress", BASE_SHA="base", HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json",
                     PUBLISH_STEP="COMPLETE", ARCHIVE_DIGEST="archive", PUBLISH_STEP_RECEIPTS=prefix + [{"STEP": "COMPLETE"}],
                     NEXT_STATE="DONE")
        self.assertEqual(self.transition("STEP_PASS").returncode, 0)
        self.assertEqual(json.loads(self.state_path.read_text(encoding="utf-8"))["STATE"], "DONE")

    def test_step_pass_replays_an_identical_persisted_receipt(self):
        receipts = [{"STEP": "PREFLIGHT"}]
        self.write_state(STATE="PUBLISHING", CHANGE="change", PROPOSAL_DIGEST="proposal", PROGRESS_DIGEST="progress",
                         BASE_SHA="base", HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json", PUBLISH_STEP_RECEIPTS=receipts)
        self.handoff(OWNER="Archivist / Publisher", CHANGE="change", PROPOSAL_DIGEST="proposal",
                     PROGRESS_DIGEST="progress", BASE_SHA="base", HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json",
                     PUBLISH_STEP="PREFLIGHT", ARCHIVE_DIGEST="archive", PUBLISH_STEP_RECEIPTS=receipts,
                     NEXT_STATE="PUBLISHING")
        result = self.transition("STEP_PASS")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.state_path.read_text(encoding="utf-8"))["PUBLISH_STEP_RECEIPTS"], receipts)

    def test_step_pass_replays_same_handoff_before_and_after_complete(self):
        preflight = [{"STEP": "PREFLIGHT"}]
        self.write_state(STATE="PUBLISHING", CHANGE="change", PROPOSAL_DIGEST="proposal", PROGRESS_DIGEST="progress",
                         BASE_SHA="base", HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json", PUBLISH_STEP_RECEIPTS=[])
        self.handoff(OWNER="Archivist / Publisher", CHANGE="change", PROPOSAL_DIGEST="proposal",
                     PROGRESS_DIGEST="progress", BASE_SHA="base", HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json",
                     PUBLISH_STEP="PREFLIGHT", ARCHIVE_DIGEST="archive", PUBLISH_STEP_RECEIPTS=preflight,
                     NEXT_STATE="PUBLISHING")
        self.assertEqual(self.transition("STEP_PASS").returncode, 0)
        accepted = json.loads(self.state_path.read_text(encoding="utf-8"))["HANDOFFS"][0]
        altered = dict(accepted)
        altered["SUMMARY"] = "altered"
        self.handoff_path.write_text(json.dumps(altered), encoding="utf-8")
        before_rejection = self.state_path.read_bytes()
        self.assert_json_error_and_unchanged(self.transition("STEP_PASS"), before_rejection)
        self.handoff_path.write_text(json.dumps(accepted), encoding="utf-8")
        before_replay = self.state_path.read_bytes()
        replay = self.transition("STEP_PASS")
        self.assertEqual(replay.returncode, 0, replay.stderr)
        self.assertEqual(self.state_path.read_bytes(), before_replay)

        prefix = [{"STEP": step} for step in ("PREFLIGHT", "ARCHIVE", "VALIDATE", "FINAL_COMMIT", "PUSH", "LINEAR_SYNC")]
        self.write_state(STATE="PUBLISHING", CHANGE="change", PROPOSAL_DIGEST="proposal", PROGRESS_DIGEST="progress",
                         BASE_SHA="base", HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json", PUBLISH_STEP_RECEIPTS=prefix)
        complete = prefix + [{"STEP": "COMPLETE"}]
        self.handoff(OWNER="Archivist / Publisher", CHANGE="change", PROPOSAL_DIGEST="proposal",
                     PROGRESS_DIGEST="progress", BASE_SHA="base", HEAD_SHA="head", APPROVAL_ARTIFACT="approval.json",
                     PUBLISH_STEP="COMPLETE", ARCHIVE_DIGEST="archive", PUBLISH_STEP_RECEIPTS=complete,
                     NEXT_STATE="DONE")
        self.assertEqual(self.transition("STEP_PASS").returncode, 0)
        before_done_replay = self.state_path.read_bytes()
        replay = self.transition("STEP_PASS")
        self.assertEqual(replay.returncode, 0, replay.stderr)
        self.assertEqual(self.state_path.read_bytes(), before_done_replay)

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
        handoff_path = self.root / "no-origin-handoff.json"
        handoff_path.write_text("{}", encoding="utf-8")
        before = state_path.read_bytes()
        result = self.invoke(
            "publish-receipt", "--state", str(state_path), "--handoff", str(handoff_path),
            "--step", "PREFLIGHT", "--result-file", str(receipt),
        )
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
        existing = {
            "STEP": "PREFLIGHT", "RESULT_FILE": str(result_file.resolve()),
            "RESULT_DIGEST": hashlib.sha256(result_file.read_bytes()).hexdigest(),
        }
        self.write_state(STATE="PUBLISHING", PUBLISH_STEP_RECEIPTS=[existing])
        self.handoff_path.write_text(json.dumps({
            "PUBLISH_STEP_RECEIPTS": [{**existing, "ARCHIVE_DIGEST": "different"}],
        }), encoding="utf-8")
        before = self.state_path.read_bytes()
        result = self.invoke(
            "publish-receipt", "--state", str(self.state_path), "--handoff", str(self.handoff_path),
            "--step", "PREFLIGHT", "--result-file", str(result_file), "--archive-digest", "different",
        )
        self.assert_json_error_and_unchanged(result, before)


class WorkflowStateFinalRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state_path = self.root / "state.json"
        self.handoff_path = self.root / "handoff.json"

    def invoke(self, command, *arguments):
        return subprocess.run([sys.executable, str(SCRIPT), command, "--state", str(self.state_path),
                               *arguments], text=True, capture_output=True)

    def stage(self, current, **overrides):
        state = {
            "RUN_ID": "run-final", "STATE": current, "ATTEMPT_ID": "attempt-old",
            "CHANGE": "change", "REQUEST_ARTIFACT": "request.md",
            "APPROVAL_ARTIFACT": "approval.json", "APPROVAL_DIGEST": "approval",
            "PROPOSAL_DIGEST": "proposal", "PROGRESS_DIGEST": "progress",
            "BASE_SHA": "base", "HEAD_SHA": "head", "UNTRACKED_BASELINE": ["user.db"],
            "PUBLISH_STEP_RECEIPTS": [], "PUBLISH_AUTHORIZED": False,
        }
        state.update(overrides)
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        return state

    def candidate(self, owner, target, **overrides):
        state = json.loads(self.state_path.read_text())
        payload = {
            field: state.get(field) for field in (
                "RUN_ID", "ATTEMPT_ID", "CHANGE", "REQUEST_ARTIFACT", "APPROVAL_ARTIFACT",
                "APPROVAL_DIGEST", "PROPOSAL_DIGEST", "PROGRESS_DIGEST", "BASE_SHA", "HEAD_SHA",
                "UNTRACKED_BASELINE", "PUBLISH_STEP_RECEIPTS", "ARCHIVE_DIGEST",
            )
        }
        payload.update(OWNER=owner, STATUS="PASS", NEXT_STATE=target,
                       SUMMARY="result", EVIDENCE=[], BLOCKERS=[], ARTIFACTS=[])
        payload.update(overrides)
        self.handoff_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def accept(self, event="PASS"):
        for command in ("validate-handoff", "transition"):
            result = self.invoke(command, "--event", event, "--handoff", str(self.handoff_path))
            self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(self.state_path.read_text())

    def reject(self, event="PASS", error=None):
        before = self.state_path.read_bytes()
        for command in ("validate-handoff", "transition"):
            result = self.invoke(command, "--event", event, "--handoff", str(self.handoff_path))
            self.assertNotEqual(result.returncode, 0, result.stdout)
            if error:
                self.assertIn(error, json.loads(result.stderr)["error"])
            self.assertEqual(self.state_path.read_bytes(), before)

    def test_apply_and_fix_accept_new_progress_and_committed_head(self):
        for current in ("APPLYING", "FIXING_IMPLEMENTATION"):
            with self.subTest(current=current):
                self.stage(current)
                self.candidate("Apply Executor", "AUDITING", HEAD_SHA="new-head", PROGRESS_DIGEST="completed")
                saved = self.accept()
                self.assertEqual(saved["HEAD_SHA"], "new-head")
                self.assertEqual(saved["PROGRESS_DIGEST"], "completed")
                self.assertEqual(saved["PROPOSAL_DIGEST"], "proposal")
                self.candidate("Pre-Archive Auditor", "READY_TO_PUBLISH")
                self.assertEqual(self.accept()["STATE"], "READY_TO_PUBLISH")

    def test_revision_updates_proposal_before_rereview(self):
        self.stage("REVISING_PROPOSAL")
        self.candidate("Explore / Proposal", "REVIEWING_PROPOSAL",
                       PROPOSAL_DIGEST="revised", PROGRESS_DIGEST="revised-tasks")
        saved = self.accept()
        self.assertEqual(saved["PROPOSAL_DIGEST"], "revised")
        self.candidate("Proposal Reviewer", "APPLYING")
        self.assertEqual(self.accept()["PROPOSAL_DIGEST"], "revised")

    def test_revise_explore_accepts_new_result_and_invalidates_old_approval(self):
        old_result = self.root / "old.md"
        new_result = self.root / "new.md"
        old_result.write_text("old direction")
        new_result.write_text("new direction")
        self.stage("AWAITING_EXPLORE_APPROVAL", CHANGE=None, PROPOSAL_DIGEST=None, PROGRESS_DIGEST=None,
                   EXPLORE_ARTIFACT=str(old_result), EXPLORE_DIGEST=hashlib.sha256(old_result.read_bytes()).hexdigest(),
                   PUBLISH_AUTHORIZED=True)
        result = self.invoke("transition", "--event", "REVISE")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.candidate("Explore / Proposal", "AWAITING_EXPLORE_APPROVAL",
                       EXPLORE_ARTIFACT=str(new_result), EXPLORE_DIGEST=hashlib.sha256(new_result.read_bytes()).hexdigest())
        saved = self.accept()
        self.assertEqual(saved["EXPLORE_ARTIFACT"], str(new_result))
        self.assertIsNone(saved["APPROVAL_DIGEST"])
        self.assertIsNone(saved["APPROVAL_ARTIFACT"])
        self.assertFalse(saved["PUBLISH_AUTHORIZED"])

    def test_nonproducing_stages_reject_changed_bindings(self):
        cases = (
            ("APPLYING", "Apply Executor", "AUDITING", "PROPOSAL_DIGEST"),
            ("FIXING_IMPLEMENTATION", "Apply Executor", "AUDITING", "BASE_SHA"),
            ("REVIEWING_PROPOSAL", "Proposal Reviewer", "APPLYING", "PROPOSAL_DIGEST"),
            ("AUDITING", "Pre-Archive Auditor", "READY_TO_PUBLISH", "PROPOSAL_DIGEST"),
            ("AUDITING", "Pre-Archive Auditor", "READY_TO_PUBLISH", "PROGRESS_DIGEST"),
            ("AUDITING", "Pre-Archive Auditor", "READY_TO_PUBLISH", "HEAD_SHA"),
            ("PUBLISHING", "Archivist / Publisher", "BLOCKED", "HEAD_SHA"),
            ("PUBLISHING", "Archivist / Publisher", "BLOCKED", "PROGRESS_DIGEST"),
        )
        for current, owner, target, field in cases:
            with self.subTest(current=current, field=field):
                self.stage(current)
                extra = {"STATUS": "BLOCKED", "PUBLISH_STEP": "PREFLIGHT"} if current == "PUBLISHING" else {}
                self.candidate(owner, target, **{field: "changed"}, **extra)
                self.reject("BLOCKED" if current == "PUBLISHING" else "PASS", "mismatched " + field)

    def test_proposal_changed_handoffs_route_both_scopes_and_legacy_aliases(self):
        cases = (
            ("PROPOSAL_CHANGED", "WITHIN_APPROVED_SCOPE", "REVIEWING_PROPOSAL"),
            ("PROPOSAL_CHANGED", "OUTSIDE_APPROVED_SCOPE", "EXPLORING"),
            ("PROPOSAL_CHANGED_WITHIN_SCOPE", None, "REVIEWING_PROPOSAL"),
            ("PROPOSAL_CHANGED_OUTSIDE_SCOPE", None, "EXPLORING"),
        )
        for event, scope, target in cases:
            with self.subTest(event=event, scope=scope):
                self.stage("APPLYING", PUBLISH_AUTHORIZED=True)
                self.candidate("Apply Executor", target, SCOPE=scope, PROPOSAL_DIGEST="changed-proposal")
                saved = self.accept(event)
                self.assertEqual(saved["STATE"], target)
                self.assertEqual(saved["PROPOSAL_DIGEST"], "changed-proposal")
                if target == "REVIEWING_PROPOSAL":
                    self.candidate("Proposal Reviewer", "APPLYING")
                    self.assertEqual(self.accept()["STATE"], "APPLYING")
                else:
                    self.assertIsNone(saved["APPROVAL_DIGEST"])
                    self.assertFalse(saved["PUBLISH_AUTHORIZED"])
                    explore = self.root / "scope.md"
                    explore.write_text("reconsidered direction")
                    self.candidate("Explore / Proposal", "AWAITING_EXPLORE_APPROVAL",
                                   EXPLORE_ARTIFACT=str(explore), EXPLORE_DIGEST=hashlib.sha256(explore.read_bytes()).hexdigest())
                    self.assertEqual(self.accept()["CHANGE"], "change")

    def test_proposal_changed_rejects_invalid_scope_status_and_owner(self):
        for overrides in ({"SCOPE": None}, {"SCOPE": "unknown"}, {"STATUS": "NEEDS_HUMAN"},
                          {"OWNER": "Proposal Reviewer"}, {"NEXT_STATE": "AUDITING"}):
            with self.subTest(overrides=overrides):
                self.stage("APPLYING")
                values = {"SCOPE": "WITHIN_APPROVED_SCOPE", "PROPOSAL_DIGEST": "changed", **overrides}
                self.candidate(values.pop("OWNER", "Apply Executor"),
                               values.pop("NEXT_STATE", "REVIEWING_PROPOSAL"), **values)
                self.reject("PROPOSAL_CHANGED")
        self.stage("APPLYING")
        self.candidate("Apply Executor", "EXPLORING", SCOPE="OUTSIDE_APPROVED_SCOPE")
        self.reject("PROPOSAL_CHANGED_WITHIN_SCOPE")

    def test_needs_human_handoff_preserves_recoverable_stage(self):
        for current, owner in (("EXPLORING", "Explore / Proposal"), ("APPLYING", "Apply Executor"),
                               ("AUDITING", "Pre-Archive Auditor")):
            with self.subTest(current=current):
                extra = {"CHANGE": None, "PROPOSAL_DIGEST": None, "PROGRESS_DIGEST": None} if current == "EXPLORING" else {}
                self.stage(current, **extra)
                self.candidate(owner, "NEEDS_HUMAN", STATUS="NEEDS_HUMAN", BLOCKERS=["human decision required"])
                saved = self.accept("NEEDS_HUMAN")
                self.assertEqual(saved["STATE"], "NEEDS_HUMAN")
                self.assertEqual(saved["RESUME_STATE"], current)
                evidence = self.root / "decision.md"
                evidence.write_text("human resolved the decision")
                result = self.invoke("transition", "--event", "RESOLVE_BLOCKER", "--evidence", str(evidence))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["STATE"], current)

    def test_post_gate_handoffs_require_the_saved_approval_digest(self):
        stages = (
            ("PROPOSING", "Explore / Proposal", "REVIEWING_PROPOSAL"),
            ("REVISING_PROPOSAL", "Explore / Proposal", "REVIEWING_PROPOSAL"),
            ("REVIEWING_PROPOSAL", "Proposal Reviewer", "APPLYING"),
            ("APPLYING", "Apply Executor", "AUDITING"),
            ("FIXING_IMPLEMENTATION", "Apply Executor", "AUDITING"),
            ("AUDITING", "Pre-Archive Auditor", "READY_TO_PUBLISH"),
            ("PUBLISHING", "Archivist / Publisher", "BLOCKED"),
        )
        for current, owner, target in stages:
            for digest in (None, "", "changed", "absent"):
                with self.subTest(current=current, digest=digest):
                    self.stage(current)
                    extra = {"STATUS": "BLOCKED", "PUBLISH_STEP": "PREFLIGHT"} if current == "PUBLISHING" else {}
                    payload = self.candidate(owner, target, APPROVAL_DIGEST=digest, **extra)
                    if digest == "absent":
                        del payload["APPROVAL_DIGEST"]
                        self.handoff_path.write_text(json.dumps(payload))
                    self.reject("BLOCKED" if current == "PUBLISHING" else "PASS")
        self.stage("PROPOSING", APPROVAL_DIGEST=None)
        self.candidate("Explore / Proposal", "REVIEWING_PROPOSAL", APPROVAL_DIGEST="unapproved")
        self.reject()

    def test_later_publish_authorization_is_bound_and_persisted_before_routing(self):
        approval = self.root / "approval.json"
        approval.write_text('{"PUBLISH_AUTHORIZED": false}')
        evidence = self.root / "publish-decision.md"
        evidence.write_text("User explicitly authorized publishing this audited Change")
        initial = self.stage("AUDITING", PROJECT_REALPATH=str(self.root), BRANCH="main",
                             REMOTE_URL="https://example.test/repo.git", APPROVAL_ARTIFACT=str(approval),
                             APPROVAL_DIGEST=hashlib.sha256(approval.read_bytes()).hexdigest())
        self.candidate("Pre-Archive Auditor", "READY_TO_PUBLISH")
        self.accept()
        result = self.invoke("authorize-publish", "--evidence", str(evidence))
        self.assertEqual(result.returncode, 0, result.stderr)
        authorized = json.loads(result.stdout)
        self.assertEqual(authorized["STATE"], "READY_TO_PUBLISH")
        self.assertTrue(authorized["PUBLISH_AUTHORIZED"])
        self.assertEqual(authorized["APPROVAL_DIGEST"], initial["APPROVAL_DIGEST"])
        self.assertEqual(approval.read_text(), '{"PUBLISH_AUTHORIZED": false}')
        record = authorized["PUBLISH_AUTHORIZATION"]
        for field in PUBLISH_AUTHORIZATION_FIELDS:
            self.assertEqual(record[field], initial[field])
        self.assertEqual(record["EVIDENCE"]["DIGEST"], hashlib.sha256(evidence.read_bytes()).hexdigest())
        self.assertIn("AUTHORIZED_AT", record)
        result = self.invoke("transition", "--event", "AUTHORIZE_PUBLISH")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["STATE"], "PUBLISHING")
        self.assertTrue(json.loads(result.stdout)["PUBLISH_AUTHORIZED"])

    def test_later_publish_authorization_accepts_and_binds_empty_baseline(self):
        evidence = self.root / "decision.md"
        evidence.write_text("publish")
        self.stage("READY_TO_PUBLISH", PROJECT_REALPATH=str(self.root), BRANCH="main",
                   REMOTE_URL="https://example.test/repo.git", UNTRACKED_BASELINE=[])
        result = self.invoke("authorize-publish", "--evidence", str(evidence))
        self.assertEqual(result.returncode, 0, result.stderr)
        authorized = json.loads(result.stdout)
        self.assertEqual(authorized["PUBLISH_AUTHORIZATION"]["UNTRACKED_BASELINE"], [])
        result = self.invoke("transition", "--event", "AUTHORIZE_PUBLISH")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["STATE"], "PUBLISHING")

    def test_later_publish_authorization_requires_ready_state_evidence_and_bindings(self):
        evidence = self.root / "decision.md"
        evidence.write_text("publish")
        for current, overrides, artifact in (
            ("READY_TO_PUBLISH", {}, self.root / "missing.md"),
            ("APPLYING", {}, evidence),
            ("PUBLISHING", {}, evidence),
            ("READY_TO_PUBLISH", {"APPROVAL_DIGEST": None}, evidence),
            ("READY_TO_PUBLISH", {"HEAD_SHA": None}, evidence),
        ):
            with self.subTest(current=current, overrides=overrides):
                self.stage(current, PROJECT_REALPATH=str(self.root), BRANCH="main",
                           REMOTE_URL="https://example.test/repo.git", **overrides)
                before = self.state_path.read_bytes()
                result = self.invoke("authorize-publish", "--evidence", str(artifact))
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.state_path.read_bytes(), before)
        self.stage("READY_TO_PUBLISH")
        before = self.state_path.read_bytes()
        result = self.invoke("transition", "--event", "AUTHORIZE_PUBLISH")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_later_authorization_rejects_changed_scope_before_publishing(self):
        evidence = self.root / "decision.md"
        evidence.write_text("publish this audited Change")
        for field in ("HEAD_SHA", "PROGRESS_DIGEST", "PROPOSAL_DIGEST", "APPROVAL_DIGEST", "BRANCH",
                      "REMOTE_URL", "UNTRACKED_BASELINE"):
            with self.subTest(field=field):
                self.stage("READY_TO_PUBLISH", PROJECT_REALPATH=str(self.root), BRANCH="main",
                           REMOTE_URL="https://example.test/repo.git")
                result = self.invoke("authorize-publish", "--evidence", str(evidence))
                self.assertEqual(result.returncode, 0, result.stderr)
                changed = json.loads(result.stdout)
                changed[field] = ["different.db"] if field == "UNTRACKED_BASELINE" else "different"
                self.state_path.write_text(json.dumps(changed))
                before = self.state_path.read_bytes()
                result = self.invoke("transition", "--event", "AUTHORIZE_PUBLISH")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.state_path.read_bytes(), before)

    def test_archive_can_block_before_any_archive_receipt_or_digest_exists(self):
        receipts = [{"STEP": "PREFLIGHT"}]
        self.stage("PUBLISHING", PUBLISH_STEP_RECEIPTS=receipts)
        self.candidate("Archivist / Publisher", "BLOCKED", STATUS="BLOCKED", PUBLISH_STEP="ARCHIVE",
                       ARCHIVE_DIGEST=None, BLOCKERS=["archive command unavailable"])
        saved = self.accept("BLOCKED")
        self.assertEqual(saved["RESUME_STATE"], "PUBLISHING")
        self.assertEqual(saved["PUBLISH_STEP_RECEIPTS"], receipts)

    def test_resume_dispatch_rotates_normal_attempt_and_rejects_old_handoffs(self):
        stages = (
            ("EXPLORING", "Explore / Proposal", "AWAITING_EXPLORE_APPROVAL"),
            ("PROPOSING", "Explore / Proposal", "REVIEWING_PROPOSAL"),
            ("REVISING_PROPOSAL", "Explore / Proposal", "REVIEWING_PROPOSAL"),
            ("REVIEWING_PROPOSAL", "Proposal Reviewer", "APPLYING"),
            ("APPLYING", "Apply Executor", "AUDITING"),
            ("FIXING_IMPLEMENTATION", "Apply Executor", "AUDITING"),
            ("AUDITING", "Pre-Archive Auditor", "READY_TO_PUBLISH"),
        )
        explore = self.root / "explore.md"
        explore.write_text("direction")
        for current, owner, target in stages:
            with self.subTest(current=current):
                initial = self.stage(current)
                extra = {"EXPLORE_ARTIFACT": str(explore), "EXPLORE_DIGEST": hashlib.sha256(explore.read_bytes()).hexdigest()}
                self.candidate(owner, target, **extra)
                result = self.invoke("dispatch")
                self.assertEqual(result.returncode, 0, result.stderr)
                dispatched = json.loads(result.stdout)
                uuid.UUID(dispatched["ATTEMPT_ID"])
                self.assertNotEqual(dispatched["ATTEMPT_ID"], initial["ATTEMPT_ID"])
                self.assertEqual({**dispatched, "ATTEMPT_ID": initial["ATTEMPT_ID"]}, initial)
                self.reject(error="stale ATTEMPT_ID")
                self.candidate(owner, target, **extra)
                self.assertEqual(self.accept()["STATE"], target)

    def test_dispatch_cannot_bypass_gates_blockers_or_publish_receipts(self):
        for current in ("NEW", "AWAITING_EXPLORE_APPROVAL", "READY_TO_PUBLISH", "PUBLISHING",
                        "BLOCKED", "NEEDS_HUMAN", "DONE", "CANCELLED"):
            with self.subTest(current=current):
                self.stage(current)
                before = self.state_path.read_bytes()
                result = self.invoke("dispatch")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.state_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
