## 1. Encode the target contracts in tests

- [x] 1.1 Update static contract tests to require exactly the five expected TOML profiles, complete embedded role boundaries, no specialist Markdown references, concise progressive orchestration guidance, and no `agents/team` directory; verify the focused contract tests fail against the old split structure before implementation.
- [x] 1.2 Update bootstrap and doctor fixtures/assertions to expect only the `.agents/shared` link and no `.agents/team` link; verify the focused link-project and doctor tests fail against the old bootstrap behavior before implementation.

## 2. Consolidate specialist definitions

- [x] 2.1 Merge each specialist's non-duplicated input, read, write, forbidden, output, and escalation responsibilities into its existing TOML `developer_instructions`, preserving all five names, filenames, models, reasoning efforts, sandbox modes, installation paths, and shared/project contract references; verify all profiles parse with `tomllib` and pass the focused profile contract tests.
- [x] 2.2 Remove the five superseded specialist role Markdown files after confirming every unique responsibility is represented in the corresponding TOML; verify repository searches find no TOML or workflow reference to the removed role paths.

## 3. Consolidate orchestration and project wiring

- [x] 3.1 Reconcile the unique Orchestrator invariants into `skills/openspec-dev-team/SKILL.md`, remove redundant wording, and make canonical reference loading operation-specific without relaxing the existing skill-size guardrail; verify focused orchestration documentation tests cover ownership, forbidden actions, escalation, and progressive disclosure.
- [x] 3.2 Remove `agents/team/orchestrator.md` and the now-empty `agents/team` directory, then update `link-project.sh` and `doctor.sh` to stop creating or requiring `.agents/team`; verify link-project and doctor test suites pass with the simplified `.agents` structure.

## 4. Align documentation

- [x] 4.1 Update the root README installation, bootstrap, configuration model, diagnostics, and removal guidance to state that TOML is the sole specialist definition and `.agents/team` is obsolete; verify README contract tests pass and all documented Codex Agent links remain unchanged.
- [x] 4.2 Update Pi and Claude Code template documentation only where it references deleted team-role contracts, retaining their `template-only` status and avoiding new runtime claims; verify platform mapping tests pass.

## 5. Validate compatibility

- [x] 5.1 Run `python3 -m unittest discover -s tests` and verify all repository tests pass without references to the removed structure.
- [x] 5.2 Run `scripts/doctor.sh --global` and project bootstrap/diagnostic checks against a clean fixture, verifying all five TOMLs and the shared-only project wiring are accepted.
- [x] 5.3 Run the documented `$openspec-dev-team smoke` flow in a fresh Codex session and verify sequential discovery and no-write handoffs for all five unchanged Agent names.
- [x] 5.4 Run `openspec validate consolidate-codex-agent-definitions --strict` and verify the completed change artifacts satisfy the OpenSpec schema.
