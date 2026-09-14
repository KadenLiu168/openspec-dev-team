## Why

Codex specialist behavior is currently split between native TOML profiles and role-specific Markdown contracts, so a single Agent has multiple configuration sources that can drift. The MVP should reduce this indirection now and align each specialist with Codex native discovery while preserving the existing OpenSpec workflow and shared guarantees.

## What Changes

- Make each of the five default Codex specialist TOML profiles the sole definition of that Agent's identity, runtime settings, and role-specific instructions.
- Move non-duplicated specialist responsibilities from `agents/team/*.md` into the corresponding TOML profiles, then remove those role files.
- Fold the Orchestrator's non-duplicated invariants into the orchestration skill without copying redundant detail or forcing all phase-specific references into the initial skill context.
- Preserve detailed state transitions and cross-Agent contracts in their existing layered references so the skill can use progressive disclosure.
- Remove the obsolete `agents/team` project link and update installation diagnostics, documentation, and tests to match the simplified structure.
- Keep Codex custom-agent discovery names, model assignments, reasoning effort, sandbox modes, workflow behavior, and Human Gates unchanged.

## Capabilities

### New Capabilities

- `codex-agent-configuration`: Defines the single-TOML source-of-truth and progressive orchestration-loading requirements for the five default Codex specialists.

### Modified Capabilities

None.

## Impact

Affected areas include `profiles/codex/agents/`, `agents/team/`, the `openspec-dev-team` skill, project bootstrap and doctor scripts, root and platform mapping documentation, and contract/bootstrap/diagnostic tests. Installed Codex Agent filenames and discovery locations remain compatible; bootstrapped projects no longer require `.agents/team`.
