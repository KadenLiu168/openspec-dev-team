## Why

The root `AGENTS.md` currently repeats the five individual Codex profile filenames even though `profiles/codex/agents/` is the canonical authored source. It also describes `scripts/doctor.sh` without its required mode, and no contract test protects these repository-instruction invariants, allowing documentation drift to recur.

## What Changes

- Remove the itemized five-profile roster from the root `AGENTS.md` and retain `profiles/codex/agents/` as the canonical source reference.
- Replace the bare `scripts/doctor.sh` verification reference with wording that directs maintainers to run applicable diagnostics using their documented invocation, including the required mode when applicable.
- Add an `AGENTS.md` invariant regression test to `tests/test_contracts.py` that protects the canonical profile-source reference, prevents reintroducing the individual roster, and checks the diagnostic-invocation guidance.
- Preserve all runtime behavior, existing profile definitions, OpenSpec requirements, installation behavior, and diagnostic implementation.

## Capabilities

### New Capabilities

- None. This is a repository-instruction and contract-test alignment.

### Modified Capabilities

- None. Existing OpenSpec requirements already describe the unchanged runtime and installation behavior; this Change does not alter those requirements.

## Impact

- Implementation targets: root `AGENTS.md` and `tests/test_contracts.py`.
- Verification: focused contract tests, the applicable repository test suite, documented diagnostics, strict OpenSpec validation, and a scoped diff check.
- No production/runtime code, profile TOML, skill, script, living spec, archived Change, dependency, or external-system behavior changes.
