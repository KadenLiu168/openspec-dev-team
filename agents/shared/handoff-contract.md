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
| After Human Gate | `APPROVAL_ARTIFACT` and nonempty `APPROVAL_DIGEST` matching the saved approval binding. |
| Publishing | current step and completed `PUBLISH_STEP_RECEIPTS`; `ARCHIVE_DIGEST` is required once an archive receipt exists. |

Proposal Reviewer `PASS` binds `PROPOSAL_DIGEST`; normal task completion only
changes `PROGRESS_DIGEST` and does not invalidate that review. Auditor `PASS`
binds `PROPOSAL_DIGEST`, `PROGRESS_DIGEST`, `BASE_SHA`, `HEAD_SHA`, and the
non-ignored untracked baseline. Publisher must confirm those bindings remain
equal before publishing.

Both Human Gate and later `READY_TO_PUBLISH` authorization produce the same
`PUBLISH_AUTHORIZATION` record shape. It binds the complete
`UNTRACKED_BASELINE` list (including an empty list); Audit completes the
Change/digest/SHA values for gate-time authorization before direct Publishing.

Producing stages can replace only their outputs: Propose/revision may update
proposal/progress digests; Apply/fix may update progress and `HEAD_SHA`. Proposal
Review compares against the latest proposal handoff. Audit and Publisher reject
changes to all bound proposal/progress/SHA inputs. `BASE_SHA` and the untracked
baseline remain immutable. Re-Explore may produce a new Explore artifact/digest;
an existing Change and its digests remain bound during re-exploration. Returning
to Explore clears approval and publish authorization and requires a new Human Gate.

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

`PROPOSAL_CHANGED` is an event with `STATUS=PASS`, a new `PROPOSAL_DIGEST`, and
required `SCOPE=WITHIN_APPROVED_SCOPE|OUTSIDE_APPROVED_SCOPE`. The CLI also accepts
the legacy `PROPOSAL_CHANGED_WITHIN_SCOPE`/`PROPOSAL_CHANGED_OUTSIDE_SCOPE` event
names; an explicit scope must agree with the alias. Only Apply emits this event.
`NEEDS_HUMAN` uses the same event and status, retains the current specialist as
owner, and saves `RESUME_STATE` for evidence-based recovery. Both events use
`validate-handoff` followed by `transition --handoff`, like other handoffs.

A Publishing blocker must report exactly the persisted receipts and the first
incomplete step. A blocked `ARCHIVE` with only a `PREFLIGHT` receipt has no
required archive digest. After an `ARCHIVE` receipt exists, its digest must match.

Test evidence is a list of command, exit code, timestamp, and log path. Do not
embed complete logs in `EVIDENCE`.
