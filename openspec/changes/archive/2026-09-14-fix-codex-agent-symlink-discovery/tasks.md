## 1. Update the installation contract

- [x] 1.1 Replace the README global profile `ln -s` commands with guarded copies of all five TOMLs, keep the skill symlink unchanged, and verify the documented destinations and conflict behavior with the README contract tests
- [x] 1.2 Document refresh, migration from repository-owned profile symlinks, and removal of only source-matching regular copies; verify the guidance covers drifted and unowned destinations

## 2. Align diagnostics and focused tests

- [x] 2.1 Update `scripts/doctor.sh --global` to require non-symlink regular profile files, exact names/metadata, and byte-for-byte source matches while retaining the skill-link check; verify the doctor fixture passes for valid copies and fails for symlinks, missing files, malformed files, and drift
- [x] 2.2 Update README and doctor contract fixtures to model regular installed profiles and safe migration conflicts; verify `python3 -m unittest tests.test_contracts tests.test_doctor` passes
- [x] 2.3 Add or revise removal/install behavior tests so matching copies and repository-owned legacy profile symlinks are removable while drifted or unowned destinations are preserved; verify all ownership cases return the documented result without deleting unrelated files
- [x] 2.4 Make the unauthorized Publisher `PREFLIGHT` handoff explicitly return `STATUS=BLOCKED`, `NEXT_STATE=BLOCKED`, empty receipts, and `ARCHIVE_DIGEST=null` across the role, shared contract, state-machine reference, and smoke guidance; make validation reject a missing or non-null digest and add consistency regression coverage

## 3. Verify native compatibility

- [x] 3.1 Run `scripts/doctor.sh --global` in a clean temporary `CODEX_HOME` containing regular profile copies and verify all five profiles and the unchanged skill/project links are accepted
- [x] 3.2 Run the documented no-write smoke with an isolated temporary `CODEX_HOME`, fresh `codex exec --ephemeral --sandbox read-only` session, regular profile copies, and a disposable fixture; verify sequential native dispatch of all five exact Agent names, current handoff validation, stale `ATTEMPT_ID` rejection, unchanged fixture/project state, and unauthorized Publisher `PREFLIGHT` `BLOCKED`
- [x] 3.3 Run `python3 -m unittest discover -s tests`, strict OpenSpec validation, and `git diff --check`; verify the full applicable gates pass without changing unrelated files

## 4. Record migration readiness

- [x] 4.1 After `consolidate-codex-agent-definitions` has a stable reviewed revision, record the regular-file smoke and diagnostic evidence, update this Change’s task progress only after those gates pass, and verify its compatibility evidence can be rerun without staging consolidation-only paths or performing archive, commit, push, or external publication
