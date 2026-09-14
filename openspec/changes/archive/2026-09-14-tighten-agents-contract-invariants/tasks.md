## 1. Align root repository instructions

- [x] 1.1 Replace the five individual profile bullets in `AGENTS.md` with a directory-based statement that keeps `profiles/codex/agents/` as the canonical authored source; verify the file contains no individual name from `EXPECTED_AGENTS`.
- [x] 1.2 Update the verification expectation in `AGENTS.md` to say `run applicable diagnostics using their documented invocation`, while retaining `scripts/doctor.sh` only as a canonical path reference; verify the old bare-invocation wording is absent and the documented `--global`/`--project` modes remain the source of command detail.

## 2. Add the invariant regression test

- [x] 2.1 Extend `tests/test_contracts.py` with an `AGENTS.md` contract test that reads the root file, checks the canonical profile directory and diagnostic-guidance phrase, and derives the forbidden individual profile names from `EXPECTED_AGENTS`; verify the focused test passes and fails if a roster entry is reintroduced.

## 3. Verify the scoped change

- [x] 3.1 Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` and verify the full repository test suite passes.
- [x] 3.2 Run the applicable diagnostics with their documented invocation—`scripts/doctor.sh --global` for global installation checks or `scripts/doctor.sh --project /absolute/path/to/project` for a configured target—and verify no argument-less `doctor.sh` command is used.
- [x] 3.3 Run `openspec validate --all --strict` and `openspec validate --archived --strict`, and verify the new planning artifacts and existing specs remain valid with `skip_specs: true`.
- [x] 3.4 Run `git diff --check` and inspect the final diff to verify only `AGENTS.md` and `tests/test_contracts.py` are implementation targets, with no profile, skill, script, spec, archived Change, or external-system changes.
