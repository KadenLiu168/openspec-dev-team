"""Static contract checks for the OpenSpec development team."""

from pathlib import Path
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
CONTRACT_FILES = (WORKFLOW_POLICY, HANDOFF_CONTRACT, *ROLE_FILES, STATE_MACHINE)

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


if __name__ == "__main__":
    unittest.main()
