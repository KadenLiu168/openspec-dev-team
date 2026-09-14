"""Static contract checks for the OpenSpec development team."""

from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_POLICY = ROOT / "agents/shared/workflow-policy.md"
HANDOFF_CONTRACT = ROOT / "agents/shared/handoff-contract.md"
STATE_MACHINE = ROOT / "skills/openspec-dev-team/references/state-machine.md"
SKILL = ROOT / "skills/openspec-dev-team/SKILL.md"
README = ROOT / "README.md"
AGENTS = ROOT / "AGENTS.md"
CONTRACT_FILES = (WORKFLOW_POLICY, HANDOFF_CONTRACT, STATE_MACHINE, SKILL, README)

EXPECTED_AGENTS = {
    "openspec-explore-proposal": ("gpt-5.6-sol", "medium", "workspace-write"),
    "openspec-proposal-reviewer": ("gpt-5.6-terra", "high", "read-only"),
    "openspec-apply-executor": ("gpt-5.6-terra", "high", "workspace-write"),
    "openspec-pre-archive-auditor": ("gpt-5.6-terra", "high", "workspace-write"),
    "openspec-archivist-publisher": ("gpt-5.6-luna", "medium", "workspace-write"),
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

    def test_root_agents_preserves_profile_source_and_diagnostic_invariants(self):
        content = AGENTS.read_text()
        self.assertIn("profiles/codex/agents/", content)
        self.assertIn("run applicable diagnostics using their documented invocation", content)
        for name in EXPECTED_AGENTS:
            with self.subTest(agent=name):
                self.assertNotIn(name, content)
        verification = content.split("## Verification Expectations", 1)[1]
        self.assertNotIn("scripts/doctor.sh", verification)
        self.assertEqual(content.count("scripts/doctor.sh"), 1)

    def test_codex_profiles_are_the_exact_default_agent_set(self):
        self.assertEqual(
            sorted(path.name for path in CODEX_AGENTS.glob("*.toml")),
            sorted(name + ".toml" for name in EXPECTED_AGENTS),
        )
        self.assertFalse((ROOT / "agents/team").exists())

    def test_profiles_embed_required_role_contract_sections(self):
        for name in EXPECTED_AGENTS:
            with self.subTest(agent=name):
                content = (CODEX_AGENTS / f"{name}.toml").read_text()
                for section in ("## INPUT", "## READ", "## WRITE", "## FORBIDDEN",
                                "## OUTPUT", "## Escalation"):
                    self.assertIn(section, content)
                self.assertNotIn("agents/team/", content)

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
                self.assertNotIn("agents/team/", instructions)
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
                self.assertNotIn("agents/team/", content)
                self.assertNotIn("orchestrator.md", content)

    def test_profile_contract_paths_are_readable_from_bootstrapped_project(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init", str(project)], check=True, capture_output=True)
            subprocess.run([str(ROOT / "scripts/link-project.sh"), str(project)],
                           check=True, capture_output=True)
            for name in EXPECTED_AGENTS:
                with self.subTest(agent=name):
                    profile = tomllib.loads((CODEX_AGENTS / f"{name}.toml").read_text())
                    opening = profile["developer_instructions"].split("Outside those fixed contracts", 1)[0]
                    paths = re.findall(r"(?<![\w/])\.?agents/[\w/.-]+\.md", opening)
                    self.assertEqual(len(paths), 3)
                    resolved = [(project / path).resolve() for path in paths]
                    self.assertEqual(resolved[:2], [
                        ROOT / "agents/shared/workflow-policy.md",
                        ROOT / "agents/shared/handoff-contract.md",
                    ])
                    for path in resolved:
                        self.assertTrue(path.read_text().strip())

    def test_apply_owns_commit_of_current_reviewed_change_artifacts(self):
        profile = tomllib.loads((CODEX_AGENTS / "openspec-apply-executor.toml").read_text())
        for content in (WORKFLOW_POLICY.read_text(), profile["developer_instructions"]):
            with self.subTest(contract=content.splitlines()[0]):
                self.assertIn("approved Change artifacts (proposal, design, delta specs, and tasks)",
                              " ".join(content.split()))
                self.assertIn("PROPOSAL_DIGEST", content)
                self.assertIn("allowlist", content)
        for name in ("openspec-explore-proposal", "openspec-proposal-reviewer", "openspec-pre-archive-auditor"):
            instructions = tomllib.loads((CODEX_AGENTS / f"{name}.toml").read_text())["developer_instructions"]
            self.assertIn("Git write allowlist: none.", instructions)


class OrchestrationDocumentationTests(unittest.TestCase):
    def read_document(self, path):
        self.assertTrue(path.is_file(), f"missing {path.relative_to(ROOT)}")
        return path.read_text()

    def read_bash_block(self, content, heading):
        section = content.split(heading, 1)[1]
        block = re.search(r"```bash\n(.*?)```", section, re.S)
        self.assertIsNotNone(block)
        return block[1]

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
            "agents/shared/handoff-contract.md", "sole lifecycle", "expected owner",
            "fresh context", "full conversation", "The Orchestrator must not implement, review, or publish",
            "owns request provenance", "handoff persistence", "Escalate Human Gates",
            "third blocking findings", "instead of guessing", "operation-specific", "canonical reference",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)
        self.assertNotIn("openspec/changes/", content)
        self.assertNotIn("agents/team/", content)

    def test_skill_resolves_each_interface_from_its_canonical_root(self):
        content = self.read_document(SKILL)
        for required in (
            "SKILL_DIR", "TEAM_ROOT", "PROJECT_ROOT",
            "$SKILL_DIR/references/state-machine.md",
            "$TEAM_ROOT/agents/shared/workflow-policy.md",
            "$TEAM_ROOT/agents/shared/handoff-contract.md",
            "$PROJECT_ROOT/.agents/project.md",
            "for routing and transition decisions",
            "for workflow-boundary checks",
            "for handoff validation",
            "$TEAM_ROOT/scripts/doctor.sh",
            "$TEAM_ROOT/scripts/workflow-state.py",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

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

    def test_skill_documents_recovery_authorization_and_canonical_events(self):
        content = self.read_document(SKILL)
        for command in ("dispatch --state", "authorize-publish --state"):
            self.assertIn(command, content)
        for field in ("PROJECT_ROOT", "APPROVAL_DIGEST", "PROPOSAL_CHANGED", "WITHIN_APPROVED_SCOPE",
                      "OUTSIDE_APPROVED_SCOPE", "SCOPE", "NEEDS_HUMAN"):
            self.assertIn(field, content)
        self.assertIn("new `ATTEMPT_ID`", content)
        self.assertIn("AUTHORIZE_PUBLISH", content)
        self.assertIn("PUBLISH_AUTHORIZATION", content)
        publisher_profile = (CODEX_AGENTS / "openspec-archivist-publisher.toml").read_text()
        self.assertIn("PUBLISH_AUTHORIZATION", publisher_profile)

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
        content = self.read_document(STATE_MACHINE).split("## Publishing steps", 1)[1]
        for required in (
            "PUBLISHING", "receipt-based recovery", "actual Git/OpenSpec/Linear state",
            "before recording or continuing each receipt", "first incomplete step",
            "PUBLISH_STEP_RECEIPTS", "publish-receipt", "ARCHIVE_DIGEST", "FINAL_SHA",
            "STEP_PASS", "PREFLIGHT", "ARCHIVE", "VALIDATE", "FINAL_COMMIT", "PUSH",
            "LINEAR_SYNC", "COMPLETE", "authorization", "AUDITING",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_skill_defers_publishing_operations_to_the_phase_reference(self):
        content = self.read_document(SKILL)
        self.assertIn("references/state-machine.md#publishing-steps", content)
        self.assertIn("earlier phases do not load that section", content)
        commands = re.findall(r"^```[^\n]*\n(.*?)^```", content, re.M | re.S)
        self.assertFalse(any("publish-receipt --state" in block for block in commands))
        publishing = self.read_document(STATE_MACHINE).split("## Publishing steps", 1)[1]
        commands = re.findall(r"^```[^\n]*\n(.*?)^```", publishing, re.M | re.S)
        sequence = next(block for block in commands if "publish-receipt --state" in block)
        self.assertLess(sequence.index("validate-handoff --state"),
                        sequence.index("publish-receipt --state"))
        self.assertLess(sequence.index("publish-receipt --state"),
                        sequence.index("transition --state"))

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
            "CODEX_HOME", "--ephemeral", "read-only", "fixture/project", "attempted write",
            "BLOCKED", "do not run", "init", "approve", "transition", "publish-receipt",
            "archive", "commit", "push", "Linear",
        ):
            with self.subTest(required=required):
                self.assertIn(required, smoke)

    def test_unauthorized_publisher_preflight_contract_is_explicit(self):
        for path in (HANDOFF_CONTRACT, STATE_MACHINE, SKILL,
                     CODEX_AGENTS / "openspec-archivist-publisher.toml"):
            with self.subTest(path=path):
                content = path.read_text()
                for required in (
                    "STATUS=BLOCKED", "PUBLISH_STEP=PREFLIGHT",
                    "NEXT_STATE=BLOCKED", "PUBLISH_STEP_RECEIPTS=[]", "ARCHIVE_DIGEST=null",
                ):
                    self.assertIn(required, content)

    def test_readme_explains_purpose_prerequisites_installation_and_discovery(self):
        content = self.read_document(README)
        for required in (
            "OpenSpec", "Codex", "Python 3.11+", "Python 3.13", "Git", "main",
            "ln -s", "cp", ".codex/skills", ".codex/agents",
            "skills/openspec-dev-team", "profiles/codex/agents", "new Codex session",
            "custom-agent discovery", "template-only", "regular files",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)
        self.assertIn("`python3` resolved from `PATH` must be Python 3.11+", content)

    def test_readme_installation_preflights_every_destination_and_copies_profiles(self):
        content = self.read_document(README)
        installation = self.read_bash_block(content, "## Installation")
        for required in (
            "install_link", "install_copy", '[ -e "$path" ] || [ -L "$path" ]',
            'ln -s -- "$source" "$link"', 'cp -- "$source" "$destination"',
            "return 1", ".codex/skills/openspec-dev-team",
            "openspec-explore-proposal.toml", "openspec-proposal-reviewer.toml",
            "openspec-apply-executor.toml", "openspec-pre-archive-auditor.toml",
            "openspec-archivist-publisher.toml",
        ):
            with self.subTest(required=required):
                self.assertIn(required, installation)
        first_install = installation.index('install_link "$repository/skills/openspec-dev-team"')
        preflight = installation[:first_install]
        for destination in (
            ".codex/skills/openspec-dev-team", "openspec-explore-proposal.toml",
            "openspec-proposal-reviewer.toml", "openspec-apply-executor.toml",
            "openspec-pre-archive-auditor.toml", "openspec-archivist-publisher.toml",
        ):
            with self.subTest(preflight_destination=destination):
                self.assertIn(destination, preflight)

    def run_readme_installation(self, home):
        installation = self.read_bash_block(self.read_document(README), "## Installation")
        bin_dir = home.parent / "bin"
        bin_dir.mkdir()
        (bin_dir / "python3").symlink_to(sys.executable)
        environment = {**os.environ, "HOME": str(home),
                       "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", "")}
        return subprocess.run(
            ["/bin/bash", "-c", installation], cwd=ROOT, env=environment,
            capture_output=True, text=True,
        )

    def test_readme_installation_creates_regular_profile_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            result = self.run_readme_installation(home)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            skill = home / ".codex/skills/openspec-dev-team"
            self.assertTrue(skill.is_symlink())
            self.assertEqual(skill.resolve(), (ROOT / "skills/openspec-dev-team").resolve())
            for name in EXPECTED_AGENTS:
                installed = home / ".codex/agents" / (name + ".toml")
                with self.subTest(agent=name):
                    self.assertTrue(installed.is_file())
                    self.assertFalse(installed.is_symlink())
                    self.assertEqual(installed.read_bytes(),
                                     (CODEX_AGENTS / installed.name).read_bytes())

    def test_readme_installation_refuses_existing_destination_without_partial_install(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            conflict = home / ".codex/agents/openspec-apply-executor.toml"
            conflict.parent.mkdir(parents=True)
            conflict.write_text("user-owned\n")

            result = self.run_readme_installation(home)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Refusing existing installation path", result.stderr)
            self.assertEqual(conflict.read_text(), "user-owned\n")
            self.assertFalse((home / ".codex/skills/openspec-dev-team").exists())
            self.assertFalse((home / ".codex/agents/openspec-explore-proposal.toml").exists())

    def test_readme_documents_bootstrap_use_human_gate_and_diagnostics(self):
        content = self.read_document(README)
        for required in (
            "link-project.sh", "--dry-run", ".agents/project.md", "quality_gates",
            "project_realpath", "main_branch", "expected_remote", "openspec_root",
            "Configuration model", "native TOML", "role-specific Markdown files are not used",
            "only `.agents/shared`", "obsolete and is not", "shared-only project wiring",
            "$openspec-dev-team <request> [--publish]", "Human Gate",
            "AWAITING_EXPLORE_APPROVAL", "READY_TO_PUBLISH", "run-id",
            "doctor.sh", "--global", "--project", "$openspec-dev-team smoke",
            "PUBLISHING", "receipt", "BLOCKED", "REQUEST_ARTIFACT", "CODEX_HOME",
            "--ephemeral", "disposable fixture",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_readme_model_map_matches_all_five_profiles(self):
        content = self.read_document(README)
        for name, (model, effort, sandbox) in EXPECTED_AGENTS.items():
            with self.subTest(agent=name):
                self.assertIn(f"| `{name}` | `{model}` | `{effort}` | `{sandbox}` |", content)

    def test_readme_documents_refresh_and_safe_profile_migration(self):
        content = self.read_document(README)
        for required in (
            "rerun", "refresh", "regular profile copies", "source drift", "manual review",
            "repository-owned profile symlink", "cmp", "content-based ownership", "unowned or drifted",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def read_removal_script(self):
        content = self.read_document(README)
        return content.split("## Removal", 1)[1].split("## ", 1)[0].split(
            "```bash", 1
        )[1].split("```", 1)[0]

    def run_readme_removal(self, home, project):
        script = self.read_removal_script()
        script = script.replace("repository=/absolute/path/to/openspec-dev-team",
                                "repository=" + str(ROOT))
        script = script.replace("project=/absolute/path/to/project", "project=" + str(project))
        return subprocess.run(
            ["/bin/bash", "-eu", "-c", script],
            env={**os.environ, "HOME": str(home)}, capture_output=True, text=True,
        )

    def test_readme_removal_deletes_matching_copies_and_preserves_unrelated_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            agents = home / ".codex/agents"
            agents.mkdir(parents=True)
            for name in EXPECTED_AGENTS:
                (agents / (name + ".toml")).write_bytes(
                    (CODEX_AGENTS / (name + ".toml")).read_bytes()
                )
            unrelated = agents / "user-owned.toml"
            unrelated.write_text("keep\n")

            result = self.run_readme_removal(home, root / "project")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for name in EXPECTED_AGENTS:
                self.assertFalse((agents / (name + ".toml")).exists())
            self.assertEqual(unrelated.read_text(), "keep\n")

    def test_readme_removal_deletes_repository_owned_legacy_profile_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            agents = home / ".codex/agents"
            agents.mkdir(parents=True)
            for name in EXPECTED_AGENTS:
                (agents / (name + ".toml")).symlink_to(CODEX_AGENTS / (name + ".toml"))
            unrelated = agents / "user-owned.toml"
            unrelated.write_text("keep\n")

            result = self.run_readme_removal(home, root / "project")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for name in EXPECTED_AGENTS:
                self.assertFalse((agents / (name + ".toml")).exists())
            self.assertEqual(unrelated.read_text(), "keep\n")

    def test_readme_removal_preserves_drifted_and_unowned_destinations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            agents = home / ".codex/agents"
            agents.mkdir(parents=True)
            drifted = agents / "openspec-explore-proposal.toml"
            drifted.write_text("drifted\n")
            other_target = root / "other.toml"
            other_target.write_text("other\n")
            unowned = agents / "openspec-proposal-reviewer.toml"
            unowned.symlink_to(other_target)

            result = self.run_readme_removal(home, root / "project")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(drifted.read_text(), "drifted\n")
            self.assertTrue(unowned.is_symlink())
            self.assertEqual(unowned.resolve(), other_target.resolve())

    def test_readme_removal_is_limited_to_verified_symlinks_and_owned_copies(self):
        content = self.read_document(README)
        self.assertIn("## Removal", content)
        removal = content.split("## Removal", 1)[1]
        for required in ("-L", "readlink", "unlink", "cmp", ".codex/skills", ".codex/agents",
                         ".agents/shared", ".agents/team"):
            with self.subTest(required=required):
                self.assertIn(required, removal)
        self.assertNotIn("rm -rf", removal)


if __name__ == "__main__":
    unittest.main()
