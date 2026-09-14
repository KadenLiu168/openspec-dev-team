## Why

The root `AGENTS.md` has drifted from the current `main` repository: it names removed Agent paths and roles, documents obsolete commands, and duplicates runtime contracts already owned by the Codex profiles, orchestration skill, shared contracts, scripts, and OpenSpec artifacts. This makes repository-level instructions a competing source of truth instead of a small set of stable guardrails.

## What Changes

- Rewrite the root `AGENTS.md` as a concise repository-level instruction contract covering project scope, stable invariants, change boundaries, Git/runtime safety, canonical-source navigation, and verification expectations.
- Replace stale Agent, repository-tree, workflow, installation, and CLI claims with paths and ownership that match the current five-profile Codex architecture.
- Explicitly distinguish authored canonical sources from template-only Pi/Claude Code mappings and project-owned `.agents` configuration.
- Keep detailed Agent role contracts, state transitions, handoff rules, installation procedures, and executable validation in their existing canonical files instead of duplicating them in `AGENTS.md`.
- Preserve existing runtime behavior and OpenSpec requirements; do not modify profiles, skills, scripts, tests, living specs, or archived Changes as part of this alignment.
- Keep this Change limited to repository instruction alignment; it does not read, modify, or synchronize any external project-management system.

## Capabilities

### New Capabilities

- None. This is a repository-level instruction and documentation alignment.

### Modified Capabilities

- None. Existing OpenSpec requirements already cover the runtime contracts, and this Change does not alter their behavior.

## Impact

- Primary implementation target: root `AGENTS.md`.
- Planning and acceptance evidence: this Change's proposal, design, and tasks, plus the existing repository tests and strict OpenSpec validation.
- No production/runtime code, Agent profile, skill, script, test, living spec, archived Change, dependency, or external-system behavior changes.
