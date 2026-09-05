# Structured Handoff Contract

Every specialist returns one structured handoff. The Orchestrator is the only
writer of accepted handoffs and runtime state.

## Required fields

```text
RUN_ID
ATTEMPT_ID
STATUS
CHANGE
REQUEST_ARTIFACT
APPROVAL_ARTIFACT
SUMMARY
EVIDENCE
BLOCKERS
ARTIFACTS
PROPOSAL_DIGEST
PROGRESS_DIGEST
BASE_SHA
HEAD_SHA
PUBLISH_STEP_RECEIPTS
NEXT_STATE
```

`STATUS = PASS | FAIL | BLOCKED | NEEDS_HUMAN`.

`CHANGE = null before OpenSpec Change creation`.

`PROPOSAL_DIGEST = apply inputs with task checkboxes normalized`: hash the full
proposal, design, delta specs, and tasks input set identified by
`openspec instructions apply`; normalize only task checkbox state to incomplete.
Task wording, order, and structure remain digest inputs.

`PROGRESS_DIGEST = exact task artifact`: hash the unnormalized tasks artifact,
including actual completion state.

## Phase requirements

| Phase | Additional required values |
| --- | --- |
| Before Change creation | `RUN_ID`, `ATTEMPT_ID`; `CHANGE`, `PROPOSAL_DIGEST`, and `PROGRESS_DIGEST` are explicitly `null`. |
| After Change creation | `CHANGE`, `PROPOSAL_DIGEST`. |
| After Apply starts | `BASE_SHA`, `HEAD_SHA`, `PROGRESS_DIGEST`. |
| After Human Gate | `APPROVAL_ARTIFACT` and its digest. |
| Publishing | current step, `ARCHIVE_DIGEST`, and completed `PUBLISH_STEP_RECEIPTS`. |

Proposal Reviewer `PASS` binds `PROPOSAL_DIGEST`; normal task completion only
changes `PROGRESS_DIGEST` and does not invalidate that review. Auditor `PASS`
binds `PROPOSAL_DIGEST`, `PROGRESS_DIGEST`, `BASE_SHA`, `HEAD_SHA`, and the
non-ignored untracked baseline. Publisher must confirm those bindings remain
equal before publishing.

## Acceptance rules

The Orchestrator rejects a handoff with a wrong `RUN_ID`, stale `ATTEMPT_ID`,
unexpected owner, missing stage fields, illegal `NEXT_STATE`, or digest/SHA
mismatch. It also rejects a non-null Change or digest before the applicable
stage, or a missing required null marker. A rejected handoff does not update
runtime state.

For `BLOCKED`, preserve a validated `resume_state`; a `RESOLVED` route requires
new evidence that the blocker is removed. Any Apply change to proposal, design,
delta specs, or task text returns to `REVIEWING_PROPOSAL`; a change outside the
approved Explore scope returns to `EXPLORING` and requires a new Human Gate.

Test evidence is a list of command, exit code, timestamp, and log path. Do not
embed complete logs in `EVIDENCE`.
