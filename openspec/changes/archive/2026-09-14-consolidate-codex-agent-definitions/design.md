## Context

The five native Codex profiles currently contain runtime metadata and short developer instructions, but each instruction delegates role semantics to a matching file under `agents/team/`. The same directory also contains `orchestrator.md`, even though orchestration is performed by the parent skill rather than a native Agent. Target projects receive the entire directory through `.agents/team`, and tests enforce this split.

`SKILL.md` is already the orchestration entry point and is near its current concision limit. It also contains detail for every lifecycle phase. The consolidation must therefore absorb Orchestrator ownership semantically, not paste another contract into the always-loaded skill body. Existing `state-machine.md`, shared workflow policy, and handoff contract provide the appropriate lower layers for canonical detail.

## Goals / Non-Goals

**Goals:**

- Give each native specialist exactly one role-specific definition.
- Remove the misleading distinction between a TOML Agent profile and a Markdown role profile.
- Make the parent skill the explicit owner of Orchestrator invariants while reducing, not increasing, its initial context burden.
- Preserve shared workflow guarantees without duplicating them across five TOML files.
- Remove the project-level team-contract link and validate the resulting structure.

**Non-Goals:**

- Making each TOML fully self-contained by duplicating shared workflow or handoff text.
- Changing Agent names, models, reasoning effort, sandbox permissions, workflow states, Human Gates, or publication authorization.
- Introducing an Agent registry, runtime adapter, generated configuration, or new external dependency.
- Redesigning Pi or Claude Code runtimes; their template documentation is updated only where it describes removed files.

## Decisions

### 1. Embed role-specific contracts in the existing TOML instructions

Each specialist's `developer_instructions` will retain its current startup and Git boundary instructions and absorb the non-duplicated `INPUT`, `READ`, `WRITE`, `FORBIDDEN`, `OUTPUT`, and escalation semantics from its matching Markdown role file. The five role Markdown files will then be deleted.

The TOMLs will continue referencing `agents/shared/workflow-policy.md`, `agents/shared/handoff-contract.md`, and project-owned `.agents/project.md`. These files define shared or project-wide inputs, not alternate Agent identities.

**Alternative considered:** Inline every shared contract into every TOML. Rejected because it would duplicate high-risk workflow guarantees five times and make drift more likely.

### 2. Integrate Orchestrator invariants into a concise, layered skill

`orchestrator.md` will not be copied verbatim. Its unique invariants will be reconciled with existing `SKILL.md` statements, and duplicates will be removed. `SKILL.md` remains the orchestration entry point and describes ownership, bounded inputs and writes, forbidden specialist work, validated output handling, and escalation.

Progressive disclosure will use the existing layers:

```text
SKILL.md
  +-- concise orchestration entry and current-operation directions
  +-- references/state-machine.md      (canonical owner/transition detail)
  +-- agents/shared/workflow-policy.md (cross-phase safety boundaries)
  +-- agents/shared/handoff-contract.md (dispatch/acceptance detail)
```

The skill will avoid an unconditional instruction to preload every canonical document. It will identify which reference is needed for routing, workflow-boundary checks, or handoff validation, and keep phase-specific detail out of startup instructions when it is not needed. The existing test that constrains skill size will remain a guardrail rather than being relaxed merely to accommodate consolidation.

**Alternative considered:** Keep `orchestrator.md` as a standalone non-Agent contract. Rejected because it has one consumer, overlaps heavily with the skill, leaves a misleading `agents/team` directory, and preserves unnecessary indirection.

**Alternative considered:** Add new per-phase orchestration reference files. Rejected for this MVP because the existing state-machine and shared contracts can provide the layering without creating another documentation hierarchy.

### 3. Remove the team-contract project link

After all six files under `agents/team/` are removed, `link-project.sh`, `doctor.sh`, installation/removal documentation, and tests will stop creating or requiring `.agents/team`. `.agents/shared` remains because specialists need stable project-relative access to cross-Agent contracts.

Installed Codex TOML links remain unchanged, so native discovery compatibility is unaffected.

### 4. Test ownership and absence, not only field presence

Static tests will enumerate the exact five TOML filenames, parse every profile, verify required runtime fields and embedded role boundaries, and reject references to removed role Markdown files. Bootstrap and doctor tests will assert the new `.agents` shape. Documentation tests will ensure installation, discovery, removal, and progressive-disclosure guidance match the implemented structure.

The Codex smoke workflow remains the behavioral discovery check. Existing workflow-state tests remain unchanged unless an assertion directly names the removed structure.

## Risks / Trade-offs

- [Longer TOML instruction strings increase each specialist's prompt size] -> Include only role-specific semantics and continue referencing canonical shared contracts.
- [Condensing `SKILL.md` could omit an Orchestrator safety invariant] -> Map every unique section of `orchestrator.md` to a retained skill statement or existing canonical reference before deleting it, then test critical ownership and forbidden-action language.
- [Progressive loading can leave a required contract unread] -> Tie each reference to explicit operations: routing, workflow-boundary enforcement, or handoff validation, and cover these triggers in static tests.
- [Existing bootstrapped projects retain a stale `.agents/team` symlink] -> Document it as obsolete and make removal safe and explicit; diagnostics do not fail solely because an extra stale link remains unless it conflicts with required paths.
- [Platform template docs become misleading] -> Update only references to deleted contracts and avoid claiming Pi or Claude Code validation.

## Migration Plan

1. Expand and validate the five TOML role definitions before deleting their Markdown counterparts.
2. Reconcile unique Orchestrator invariants into a concise `SKILL.md` and make reference loading operation-specific.
3. Remove `agents/team/` and all runtime, bootstrap, diagnostic, and test dependencies on it.
4. Update root and platform template documentation to describe the new ownership model.
5. Run TOML/static contract tests, bootstrap and doctor tests, the full test suite, and the documented Codex discovery smoke test.

Rollback restores the role files, their TOML references, and the `.agents/team` bootstrap/diagnostic wiring as one coherent unit.
