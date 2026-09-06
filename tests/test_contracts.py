"""Static contract checks for the OpenSpec development team."""

from pathlib import Path
import re
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_POLICY = ROOT / "agents/shared/workflow-policy.md"
HANDOFF_CONTRACT = ROOT / "agents/shared/handoff-contract.md"
ROLE_FILES = (
    ROOT / "agents/team/orchestrator.md",
    ROOT / "agents/team/explore-proposal.md",
    ROOT / "agents/team/proposal-reviewer.md",
    ROOT / "agents/team/apply-executor.md",
    ROOT / "agents/team/pre-archive-auditor.md",
    ROOT / "agents/team/archivist-publisher.md",
)
STATE_MACHINE = ROOT / "skills/openspec-dev-team/references/state-machine.md"
SKILL = ROOT / "skills/openspec-dev-team/SKILL.md"
README = ROOT / "README.md"
CONTRACT_FILES = (WORKFLOW_POLICY, HANDOFF_CONTRACT, *ROLE_FILES, STATE_MACHINE, SKILL, README)

EXPECTED_AGENTS = {
    "openspec-explore-proposal": ("gpt-5.6-sol", "medium", "workspace-write"),
    "openspec-proposal-reviewer": ("gpt-5.6-terra", "high", "read-only"),
    "openspec-apply-executor": ("gpt-5.6-terra", "high", "workspace-write"),
    "openspec-pre-archive-auditor": ("gpt-5.6-terra", "high", "workspace-write"),
    "openspec-archivist-publisher": ("gpt-5.6-luna", "medium", "workspace-write"),
}

AGENT_ROLE_CONTRACTS = {
    "openspec-explore-proposal": "agents/team/explore-proposal.md",
    "openspec-proposal-reviewer": "agents/team/proposal-reviewer.md",
    "openspec-apply-executor": "agents/team/apply-executor.md",
    "openspec-pre-archive-auditor": "agents/team/pre-archive-auditor.md",
    "openspec-archivist-publisher": "agents/team/archivist-publisher.md",
}

CODEX_AGENTS = ROOT / "profiles/codex/agents"
PLATFORM_MAPPING_FILES = (
    ROOT / "profiles/pi/README.md",
    ROOT / "profiles/claude-code/README.md",
)

REQUIRED_HANDOFF_FIELDS = {
    "RUN_ID", "ATTEMPT_ID", "STATUS", "CHANGE",
    "REQUEST_ARTIFACT", "APPROVAL_ARTIFACT", "SUMMARY",
    "EVIDENCE", "BLOCKERS", "ARTIFACTS", "PROPOSAL_DIGEST",
    "PROGRESS_DIGEST", "BASE_SHA", "HEAD_SHA",
    "PUBLISH_STEP_RECEIPTS", "NEXT_STATE",
}

STATE_EVENT_ROWS = (
    ("NEW", "START", "EXPLORING"),
    ("EXPLORING", "PASS", "AWAITING_EXPLORE_APPROVAL"),
    ("AWAITING_EXPLORE_APPROVAL", "APPROVE", "PROPOSING"),
    ("AWAITING_EXPLORE_APPROVAL", "REVISE", "EXPLORING"),
    ("AWAITING_EXPLORE_APPROVAL", "REJECT", "CANCELLED"),
    ("PROPOSING", "PASS", "REVIEWING_PROPOSAL"),
    ("REVIEWING_PROPOSAL", "PASS", "APPLYING"),
    ("REVIEWING_PROPOSAL", "FAIL (attempt < 3)", "REVISING_PROPOSAL"),
    ("REVIEWING_PROPOSAL", "FAIL (attempt = 3)", "NEEDS_HUMAN"),
    ("REVISING_PROPOSAL", "PASS", "REVIEWING_PROPOSAL"),
    ("APPLYING", "PASS", "AUDITING"),
    ("APPLYING", "PROPOSAL_CHANGED (within approved scope)", "REVIEWING_PROPOSAL"),
    ("APPLYING", "PROPOSAL_CHANGED (outside approved scope)", "EXPLORING"),
    ("AUDITING", "PASS (publish authorized)", "PUBLISHING"),
    ("AUDITING", "PASS (publish not authorized)", "READY_TO_PUBLISH"),
    ("AUDITING", "FAIL (attempt < 3)", "FIXING_IMPLEMENTATION"),
    ("AUDITING", "FAIL (attempt = 3)", "NEEDS_HUMAN"),
    ("FIXING_IMPLEMENTATION", "PASS", "AUDITING"),
    ("READY_TO_PUBLISH", "AUTHORIZE_PUBLISH", "PUBLISHING"),
    ("Any active state", "BLOCKED", "BLOCKED"),
    ("BLOCKED", "RESOLVED", "validated resume_state"),
    ("NEEDS_HUMAN", "RETRY_PROPOSAL", "REVISING_PROPOSAL"),
    ("NEEDS_HUMAN", "RETRY_IMPLEMENTATION", "FIXING_IMPLEMENTATION"),
    ("NEEDS_HUMAN", "RESOLVE_BLOCKER", "validated resume_state"),
    ("NEEDS_HUMAN", "REVISE_DIRECTION", "EXPLORING"),
    ("NEEDS_HUMAN", "CANCEL", "CANCELLED"),
    ("PUBLISHING", "STEP_PASS", "next publish step; DONE when complete"),
)


class ContractTests(unittest.TestCase):
    def test_all_contract_files_exist(self):
        missing = [str(path.relative_to(ROOT)) for path in CONTRACT_FILES if not path.is_file()]
        self.assertEqual([], missing)

    def test_roles_declare_required_contract_sections(self):
        for role_file in ROLE_FILES:
            with self.subTest(role=role_file.name):
                content = role_file.read_text()
                for section in ("READ", "WRITE", "FORBIDDEN", "INPUT", "OUTPUT"):
                    self.assertIn(section, content)

    def test_state_machine_contains_every_design_transition(self):
        content = STATE_MACHINE.read_text()
        for current, event, next_state in STATE_EVENT_ROWS:
            with self.subTest(current=current, event=event):
                self.assertIn(f"| `{current}` | `{event}` | `{next_state}` |", content)

    def test_handoff_contract_contains_required_fields(self):
        content = HANDOFF_CONTRACT.read_text()
        for field in REQUIRED_HANDOFF_FIELDS:
            with self.subTest(field=field):
                self.assertIn(field, content)

    def test_workflow_policy_names_required_boundaries(self):
        content = WORKFLOW_POLICY.read_text()
        for requirement in (
            "OpenSpec", "Human Gate", "main", "git add .", "git add -A",
            "force-push", "reset", "clean", "history rewrite",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, content)

    def test_codex_agent_profiles_match_required_runtime_contracts(self):
        for name, expected in EXPECTED_AGENTS.items():
            with self.subTest(agent=name):
                profile_path = CODEX_AGENTS / f"{name}.toml"
                with profile_path.open("rb") as profile_file:
                    profile = tomllib.load(profile_file)

                self.assertEqual(name, profile["name"])
                self.assertTrue(profile["description"])
                instructions = profile["developer_instructions"]
                self.assertTrue(instructions)
                self.assertIn(AGENT_ROLE_CONTRACTS[name], instructions)
                self.assertEqual(
                    expected,
                    (
                        profile["model"],
                        profile["model_reasoning_effort"],
                        profile["sandbox_mode"],
                    ),
                )

    def test_platform_mappings_are_template_only(self):
        for mapping_path in PLATFORM_MAPPING_FILES:
            with self.subTest(mapping=mapping_path.parent.name):
                content = mapping_path.read_text()
                self.assertIn("template-only", content)
                self.assertNotIn("end-to-end validation", content.lower())


class OrchestrationDocumentationTests(unittest.TestCase):
    def read_document(self, path):
        self.assertTrue(path.is_file(), f"missing {path.relative_to(ROOT)}")
        return path.read_text()

    def test_skill_is_discoverable_for_openspec_team_requests_and_concise(self):
        content = self.read_document(SKILL)
        frontmatter = re.match(r"\A---\n(.*?)\n---\n", content, re.S)
        self.assertIsNotNone(frontmatter)
        self.assertRegex(frontmatter[1], r"(?m)^name: openspec-dev-team$")
        self.assertRegex(frontmatter[1], r"(?m)^description: Use when .*OpenSpec.*team.*workflow")
        self.assertLess(len(content.splitlines()), 220)

    def test_skill_routes_exact_named_agents_from_canonical_owners(self):
        content = self.read_document(SKILL)
        for owner, agent in (
            ("Explore / Proposal", "openspec-explore-proposal"),
            ("Proposal Reviewer", "openspec-proposal-reviewer"),
            ("Apply Executor", "openspec-apply-executor"),
            ("Pre-Archive Auditor", "openspec-pre-archive-auditor"),
            ("Archivist / Publisher", "openspec-archivist-publisher"),
        ):
            with self.subTest(owner=owner):
                self.assertIn(f"| {owner} | `{agent}` |", content)
        for required in (
            "references/state-machine.md", "agents/shared/workflow-policy.md",
            "agents/shared/handoff-contract.md", "agents/team/orchestrator.md",
            "sole lifecycle", "expected owner", "fresh context", "full conversation",
            "The Orchestrator must not implement, review, or publish",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)
        self.assertNotIn("openspec/changes/", content)

    def test_skill_initializes_or_resumes_project_bound_request_provenance(self):
        content = self.read_document(SKILL)
        for required in (
            ".agents/project.md", "doctor.sh", "--global", "--project",
            "workflow-state.py", "init --project", "--request", "--publish",
            "REQUEST_ARTIFACT", ".agents/state/", ".agents/runs/", "BASE_SHA",
            "UNTRACKED_BASELINE", "resume", "main", "NEEDS_HUMAN",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_skill_validates_and_persists_every_current_attempt_handoff(self):
        content = self.read_document(SKILL)
        for required in (
            "RUN_ID", "ATTEMPT_ID", "OWNER", "NEXT_STATE", "--handoff",
            "validate-handoff --state", "transition --state", "--event",
            "persist", "atomically", "rejected handoff", "BLOCKED",
            "digest --input", "--tasks", "PROPOSAL_DIGEST", "PROGRESS_DIGEST",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)
        self.assertLess(content.index("validate-handoff --state"), content.index("transition --state", content.index("validate-handoff --state")))

    def test_skill_binds_human_gate_and_evidence_based_recovery(self):
        content = self.read_document(SKILL)
        for required in (
            "pause at `AWAITING_EXPLORE_APPROVAL`", "Human Gate",
            "APPROVAL_ARTIFACT", "EXPLORE_DIGEST", "PROJECT_REALPATH",
            "BRANCH", "REMOTE_URL", "approve --state", "--explore-result",
            "--decision", "APPROVE", "REVISE", "REJECT", "--publish-authorized",
            "READY_TO_PUBLISH", "RESUME_STATE", "--evidence", "RESOLVED",
            "never retries automatically", "DONE", "CANCELLED",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_skill_supplies_bounded_openspec_and_review_inputs(self):
        content = self.read_document(SKILL)
        for required in (
            "Read `REQUEST_ARTIFACT`", "minimal artifact inputs",
            "openspec status --change", "openspec instructions", "apply",
            "planningHome", "changeRoot", "artifactPaths", "actionContext",
            "Change inputs", "direct code paths", "BASE..HEAD", "Review Findings",
            "Audit Findings", "PROPOSING", "APPLYING",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_skill_recovers_publishing_from_reconciled_receipts(self):
        content = self.read_document(SKILL)
        for required in (
            "PUBLISHING", "receipt-based recovery", "actual Git/OpenSpec/Linear state",
            "before recording or continuing each receipt", "first incomplete step",
            "PUBLISH_STEP_RECEIPTS", "publish-receipt", "ARCHIVE_DIGEST", "FINAL_SHA",
            "STEP_PASS", "PREFLIGHT", "ARCHIVE", "VALIDATE", "FINAL_COMMIT", "PUSH",
            "LINEAR_SYNC", "COMPLETE", "authorization", "AUDITING",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_smoke_is_sequential_no_write_and_checks_stale_unauthorized_handoffs(self):
        content = self.read_document(SKILL)
        self.assertIn("## Smoke", content)
        smoke = content.split("## Smoke", 1)[1]
        positions = [smoke.index(f"`{name}`") for name in EXPECTED_AGENTS]
        self.assertEqual(sorted(positions), positions)
        for required in (
            "$openspec-dev-team smoke", "no-write", "sequentially", "fixture artifacts",
            "fresh context", "current-attempt", "validate-handoff", "ATTEMPT_ID",
            "stale ATTEMPT_ID", "nonzero", "unchanged", "unauthorized preflight",
            "BLOCKED", "do not run", "init", "approve", "transition", "publish-receipt",
            "archive", "commit", "push", "Linear",
        ):
            with self.subTest(required=required):
                self.assertIn(required, smoke)

    def test_readme_explains_purpose_prerequisites_installation_and_discovery(self):
        content = self.read_document(README)
        for required in (
            "OpenSpec", "Codex", "Python 3.11+", "Python 3.13", "Git", "main",
            "ln -s", ".codex/skills", ".codex/agents", "skills/openspec-dev-team",
            "profiles/codex/agents", "new Codex session", "custom-agent discovery",
            "template-only",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_readme_documents_bootstrap_use_human_gate_and_diagnostics(self):
        content = self.read_document(README)
        for required in (
            "link-project.sh", "--dry-run", ".agents/project.md", "quality_gates",
            "project_realpath", "main_branch", "expected_remote", "openspec_root",
            "$openspec-dev-team <request> [--publish]", "Human Gate",
            "AWAITING_EXPLORE_APPROVAL", "READY_TO_PUBLISH", "run-id",
            "doctor.sh", "--global", "--project", "$openspec-dev-team smoke",
            "PUBLISHING", "receipt", "BLOCKED", "REQUEST_ARTIFACT",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_readme_model_map_matches_all_five_profiles(self):
        content = self.read_document(README)
        for name, (model, effort, sandbox) in EXPECTED_AGENTS.items():
            with self.subTest(agent=name):
                self.assertIn(f"| `{name}` | `{model}` | `{effort}` | `{sandbox}` |", content)

    def test_readme_removal_is_limited_to_verified_symlinks(self):
        content = self.read_document(README)
        self.assertIn("## Removal", content)
        removal = content.split("## Removal", 1)[1]
        for required in ("-L", "readlink", "unlink", ".codex/skills", ".codex/agents", ".agents/shared", ".agents/team"):
            with self.subTest(required=required):
                self.assertIn(required, removal)
        self.assertNotIn("rm -rf", removal)


if __name__ == "__main__":
    unittest.main()
