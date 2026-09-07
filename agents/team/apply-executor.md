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

Write only required business code, tests, and OpenSpec task completion progress.
Own the local implementation commit, including the current approved Change
artifacts (proposal, design, delta specs, and tasks) created by Explore/Proposal.
Resolve their explicit file allowlist from supplied OpenSpec status/instructions;
before staging, recompute `PROPOSAL_DIGEST` and match the latest Proposal Review
PASS. Include only reviewed artifact content and task checkbox progress, preserve
baseline untracked files, and exclude unrelated changes and runtime evidence.
Commit this entire allowlist before returning to Audit.

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
required tool. For changed proposal/design/delta specs/task text, return event
`PROPOSAL_CHANGED`, `STATUS=PASS`, and the new digest with
`SCOPE=WITHIN_APPROVED_SCOPE` or `OUTSIDE_APPROVED_SCOPE`; stop implementation
until review or the new Human Gate succeeds. Return `NEEDS_HUMAN` for a human
decision that cannot be resolved from the approved artifacts.
