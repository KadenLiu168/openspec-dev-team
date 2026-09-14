## 1. Reconcile the repository instruction contract

- [x] 1.1 Replace the stale project scope, repository layout, Agent paths, role names, and runtime metadata claims in `AGENTS.md` with the current Codex-only supported boundary and five-profile architecture; verify every referenced authored path exists on `main`.
- [x] 1.2 Add concise repository guardrails for OpenSpec-driven changes, Human control, scope boundaries, serial `main`-branch work, and Git/runtime safety without reproducing phase transitions or role contracts; verify the file contains no obsolete installation commands or generic four-role definitions.

## 2. Add canonical-source navigation without duplicating runtime facts

- [x] 2.1 Add a concern-based canonical-source map covering Agent TOMLs, model mapping, orchestration, state routing, shared contracts, executable state enforcement, bootstrap/diagnostics, OpenSpec artifacts, tests, and template-only platform mappings; verify each mapped path and template-only label against the repository.
- [x] 2.2 Remove duplicated state-machine, handoff, installation, CLI, and detailed Agent instructions from `AGENTS.md`, retaining links or path references to their canonical owners; verify `AGENTS.md` remains a guardrail/navigation document rather than a runtime specification.

## 3. Verify the scoped alignment

- [x] 3.1 Inspect the final diff and run `git diff --check`; verify the only implementation path changed is the root `AGENTS.md` and no archived Change, living spec, runtime file, test, script, or external-system artifact is modified.
- [x] 3.2 Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`; verify the existing repository contract, bootstrap, diagnostic, and workflow tests pass without test changes.
- [x] 3.3 Run `openspec validate --all --strict` and `openspec validate --archived --strict`; verify the planning Change remains valid with `skip_specs: true` and all existing specs and archived Changes remain valid.
