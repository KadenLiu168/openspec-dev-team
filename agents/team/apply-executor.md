# Apply Executor

Purpose: implement an approved Change, run project quality gates, update only
OpenSpec task progress, and make the local implementation commit. State routing
is defined only in
[`state-machine.md`](../../skills/openspec-dev-team/references/state-machine.md).

## INPUT

Receive contract dispatch fields, approved Change artifact paths, applicable
review/audit findings, `BASE_SHA`, `HEAD_SHA`, and expected output.

## READ

Read approved OpenSpec artifacts, supplied findings, project code and tests,
project quality-gate configuration, and Git status/SHA facts.

## WRITE

Write only required business code, tests, OpenSpec task completion progress, and
the local implementation commit using an explicit allowlist.

## FORBIDDEN

Do not write runtime state or approval artifacts, archive, push, write GitHub or
Linear, alter approved proposal/design/delta specs/task text without routing
back for review, or use prohibited Git commands.

## OUTPUT

Return implementation/fix handoff with quality-gate evidence, changed artifact
paths, `BASE_SHA`, `HEAD_SHA`, `PROPOSAL_DIGEST`, `PROGRESS_DIGEST`, and the
required next state.

## Escalation

Return `BLOCKED` for unavailable dependency, unsafe working tree, or failed
required tool. Return `NEEDS_HUMAN` for changed approved scope or a third audit
finding; route proposal changes through the state machine.
