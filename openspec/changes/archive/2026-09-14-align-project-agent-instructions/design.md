## Context

See `proposal.md` for the motivation and scope. The current repository already separates runtime ownership: five native Codex TOMLs define specialist roles, the `openspec-dev-team` skill owns orchestration, shared Markdown contracts define cross-Agent guarantees, `workflow-state.py` enforces local transitions and handoff bindings, and OpenSpec artifacts define the lifecycle inputs. The root `AGENTS.md` is the outlier: it still describes removed paths, a four-role workflow, and obsolete bootstrap commands while duplicating details owned by those sources.

## Goals / Non-Goals

**Goals:**

- Make `AGENTS.md` a stable repository guardrail and navigation layer rather than a second runtime contract.
- Record the current support boundary and architecture invariants without copying dynamic role, state, installation, or CLI detail.
- Give maintainers an explicit ownership map so a future fact is updated at its canonical source.
- Keep the implementation limited to the root instruction file and verify that the existing runtime remains unchanged.

**Non-Goals:**

- Do not change Agent profiles, skill behavior, state transitions, handoff validation, scripts, tests, README installation behavior, living specs, or archived Changes.
- Do not introduce a new configuration, registry, adapter, generated file, or external dependency.
- Do not turn `AGENTS.md` into a complete architecture specification, role contract, state-machine reference, installation manual, or CLI reference.
- Do not access, modify, or synchronize external project-management systems.

## Decisions

### 1. Keep `AGENTS.md` organized around stable responsibilities

The replacement will contain only: project position and supported boundary; stable development principles; architecture invariants; change and modification boundaries; Git/runtime safety; the canonical-source map; and verification expectations. Detailed procedures will be referenced by path rather than restated.

**Alternative considered:** Preserve the existing numbered sections and correct individual stale claims. Rejected because that would leave the root file as a parallel runtime specification and would preserve the wrong abstraction boundaries.

### 2. Map ownership by concern, not by repository tree

The canonical-source map will identify the owner for each kind of fact:

| Concern | Canonical source |
| --- | --- |
| Specialist identity, model, sandbox, and role instructions | `profiles/codex/agents/*.toml` |
| Logical `READ`/`WRITE` capability mapping | `profiles/codex/model-map.md` |
| Orchestration entry point and dispatch behavior | `skills/openspec-dev-team/SKILL.md` |
| State/event routing and publishing-step reference | `skills/openspec-dev-team/references/state-machine.md` |
| Cross-Agent workflow boundaries | `agents/shared/workflow-policy.md` |
| Handoff fields, digests, and acceptance rules | `agents/shared/handoff-contract.md` |
| Executable state and handoff enforcement | `scripts/workflow-state.py` |
| Installation and project bootstrap behavior | `README.md`, `scripts/link-project.sh`, `templates/project.md` |
| Global/project diagnostics | `scripts/doctor.sh` |
| Requirements, design, tasks, and lifecycle configuration | `openspec/config.yaml`, `openspec/specs/`, `openspec/changes/` |
| Regression and contract evidence | `tests/` |
| Unverified platform mappings | `profiles/pi/README.md`, `profiles/claude-code/README.md` |

The map will state that the five Codex TOMLs are the authored specialist definitions, while installed copies and project-owned `.agents` files are deployment or project configuration, not additional role sources.

**Alternative considered:** Use a full directory tree or copy current runtime facts into the map. Rejected because a tree becomes stale quickly and copied values recreate the drift this Change is intended to remove.

### 3. Treat conflicts as an instruction-contract problem first

If the root `AGENTS.md` conflicts with a canonical runtime source, the implementation will correct `AGENTS.md` and leave runtime behavior unchanged. If two runtime sources conflict, that is outside this Change and must receive its own reviewed Change rather than being resolved by wording in `AGENTS.md`.

### 4. Keep scope and verification explicit

The implementation allowlist contains only `AGENTS.md` for repository content. Verification will run the existing test suite, strict OpenSpec validation, and a focused search/diff check for obsolete paths and commands. No test assertion will be changed merely to accommodate the instruction rewrite.

## Risks / Trade-offs

- [A concise guardrail file may omit a detail a maintainer expects] -> Link the relevant canonical source in the ownership map and keep runtime contracts in their existing files.
- [A source map can itself become stale] -> Describe ownership and paths rather than copying volatile values such as model assignments, state tables, or command sequences.
- [The current root file may be consumed by tools with implicit expectations] -> Preserve the root `AGENTS.md` location and Markdown format; validate the repository after the replacement.
- [Documentation-only scope may be mistaken for a runtime change] -> Keep the proposal's `skip_specs: true` marker and verify no non-AGENTS tracked path changes.

## Migration Plan

1. Replace the root `AGENTS.md` with the scoped guardrail and canonical-source map.
2. Inspect the diff for stale paths, obsolete commands, duplicated state/role contracts, and accidental unrelated edits.
3. Run the existing tests and strict OpenSpec validation.
4. Roll back by reverting the single `AGENTS.md` change if verification exposes an incompatibility; no runtime migration is required.
