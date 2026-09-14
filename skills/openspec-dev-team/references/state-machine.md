# Canonical State Machine

This is the only complete state/event routing table. Role contracts link here
instead of copying it. The Orchestrator enforces expected owner and transition.

## State owners and required outputs

| State | Owner | Required output |
| --- | --- | --- |
| `NEW` | Orchestrator | run-id and initial state |
| `EXPLORING` | Explore / Proposal | Explore Result |
| `AWAITING_EXPLORE_APPROVAL` | Orchestrator + Human | approval, adjustment, or rejection |
| `PROPOSING` | Explore / Proposal | OpenSpec Change |
| `REVIEWING_PROPOSAL` | Proposal Reviewer | Review Findings |
| `REVISING_PROPOSAL` | Explore / Proposal | revised Change |
| `APPLYING` | Apply Executor | implementation, tests, and SHA handoff |
| `AUDITING` | Pre-Archive Auditor | Audit Findings |
| `FIXING_IMPLEMENTATION` | Apply Executor | fixes, tests, and new `HEAD_SHA` |
| `READY_TO_PUBLISH` | Orchestrator | waiting for explicit authorization |
| `PUBLISHING` | Archivist / Publisher | archive, commit, push, and sync result |
| `DONE` | none | final SHA and final evidence |
| `CANCELLED` | none | cancellation reason |
| `BLOCKED` | current specialist -> Orchestrator | blocker evidence |
| `NEEDS_HUMAN` | Orchestrator + Human | human decision and recovery state |

## Transitions

| Current state | Event | Next state |
| --- | --- | --- |
| `NEW` | `START` | `EXPLORING` |
| `EXPLORING` | `PASS` | `AWAITING_EXPLORE_APPROVAL` |
| `AWAITING_EXPLORE_APPROVAL` | `APPROVE` | `PROPOSING` |
| `AWAITING_EXPLORE_APPROVAL` | `REVISE` | `EXPLORING` |
| `AWAITING_EXPLORE_APPROVAL` | `REJECT` | `CANCELLED` |
| `PROPOSING` | `PASS` | `REVIEWING_PROPOSAL` |
| `REVIEWING_PROPOSAL` | `PASS` | `APPLYING` |
| `REVIEWING_PROPOSAL` | `FAIL (attempt < 3)` | `REVISING_PROPOSAL` |
| `REVIEWING_PROPOSAL` | `FAIL (attempt = 3)` | `NEEDS_HUMAN` |
| `REVISING_PROPOSAL` | `PASS` | `REVIEWING_PROPOSAL` |
| `APPLYING` | `PASS` | `AUDITING` |
| `APPLYING` | `PROPOSAL_CHANGED (within approved scope)` | `REVIEWING_PROPOSAL` |
| `APPLYING` | `PROPOSAL_CHANGED (outside approved scope)` | `EXPLORING` |
| `AUDITING` | `PASS (publish authorized)` | `PUBLISHING` |
| `AUDITING` | `PASS (publish not authorized)` | `READY_TO_PUBLISH` |
| `AUDITING` | `FAIL (attempt < 3)` | `FIXING_IMPLEMENTATION` |
| `AUDITING` | `FAIL (attempt = 3)` | `NEEDS_HUMAN` |
| `FIXING_IMPLEMENTATION` | `PASS` | `AUDITING` |
| `READY_TO_PUBLISH` | `AUTHORIZE_PUBLISH` | `PUBLISHING` |
| `Any active state` | `BLOCKED` | `BLOCKED` |
| `Any normal active state` | `NEEDS_HUMAN` | `NEEDS_HUMAN` |
| `BLOCKED` | `RESOLVED` | `validated resume_state` |
| `NEEDS_HUMAN` | `RETRY_PROPOSAL` | `REVISING_PROPOSAL` |
| `NEEDS_HUMAN` | `RETRY_IMPLEMENTATION` | `FIXING_IMPLEMENTATION` |
| `NEEDS_HUMAN` | `RESOLVE_BLOCKER` | `validated resume_state` |
| `NEEDS_HUMAN` | `REVISE_DIRECTION` | `EXPLORING` |
| `NEEDS_HUMAN` | `CANCEL` | `CANCELLED` |
| `PUBLISHING` | `STEP_PASS` | `next publish step; DONE when complete` |

`BLOCKED` saves `resume_state` and never retries automatically. `RESOLVED` or
`RESOLVE_BLOCKER` requires new evidence that validates that state. Proposal
review and Audit have at most two automatic remediation rounds; the third
blocking finding moves to `NEEDS_HUMAN`.

`PROPOSAL_CHANGED` uses handoff `STATUS=PASS` and requires
`SCOPE=WITHIN_APPROVED_SCOPE` or `SCOPE=OUTSIDE_APPROVED_SCOPE`. The two legacy
scope-specific event aliases remain accepted. Re-entering Explore clears the
approval and publish authorization before a new Human Gate. An explicit
`NEEDS_HUMAN` event/status saves the current stage as `RESUME_STATE`.

At `READY_TO_PUBLISH`, `authorize-publish --state <state> --evidence <file>`
records explicit human authorization bound to the current project, approval,
and audited inputs; then `AUTHORIZE_PUBLISH` can enter `PUBLISHING`.
An interrupted normal specialist stage uses `dispatch --state <state>` before
re-dispatch to atomically issue a new `ATTEMPT_ID`. This keeps the stage and all
bindings while rejecting old handoffs. Gates, blockers, terminal states, and
Publishing cannot use this dispatch command.

## Publishing steps

`PUBLISHING` proceeds only through `PREFLIGHT -> ARCHIVE -> VALIDATE ->
FINAL_COMMIT -> PUSH -> LINEAR_SYNC -> COMPLETE`. Persist a receipt immediately
after every external or non-repeatable action. On recovery, verify actual state
and continue only the first incomplete step. If archive-to-final changes include
business code, Audit PASS is invalid and the workflow returns to `AUDITING`.

Treat `PUBLISHING` as receipt-based recovery, never as replay. Reconcile the
actual Git/OpenSpec/Linear state before recording or continuing each receipt,
using the Audit binding and `PUBLISH_STEP_RECEIPTS`.

Only `openspec-archivist-publisher` performs a step. It returns a current-attempt
handoff whose final receipt is the authoritative receipt payload: step, result
path and digest, time, input digests, and applicable `ARCHIVE_DIGEST` or
`FINAL_SHA`. The Orchestrator uses that same candidate in this exact order:

```text
python3 "$TEAM_ROOT/scripts/workflow-state.py" validate-handoff --state <state> --handoff <candidate> --event STEP_PASS
python3 "$TEAM_ROOT/scripts/workflow-state.py" publish-receipt --state <state> --handoff <candidate> --step <step> --result-file <file> [--archive-digest <digest>] [--final-sha <sha>]
python3 "$TEAM_ROOT/scripts/workflow-state.py" transition --state <state> --handoff <candidate> --event STEP_PASS
```

`publish-receipt` verifies and persists the candidate's exact final receipt but
never changes lifecycle state. Only `transition` advances the event;
`COMPLETE` becomes `DONE` there. Exact replays are idempotent, while a skipped
or altered receipt is rejected without mutation.

For unauthorized preflight, accept only a handoff with
`STATUS=BLOCKED`, `PUBLISH_STEP=PREFLIGHT`, `NEXT_STATE=BLOCKED`,
`PUBLISH_STEP_RECEIPTS=[]`, and `ARCHIVE_DIGEST=null`; no archive digest exists
yet. Do not record a receipt or send `STEP_PASS`. Other invalid authorization or
bindings are also `BLOCKED`. A blocked `ARCHIVE` needs no digest before its
receipt exists; after the archive receipt, require its matching digest and the
first incomplete step.
