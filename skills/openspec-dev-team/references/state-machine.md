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

## Publishing steps

`PUBLISHING` proceeds only through `PREFLIGHT -> ARCHIVE -> VALIDATE ->
FINAL_COMMIT -> PUSH -> LINEAR_SYNC -> COMPLETE`. Persist a receipt immediately
after every external or non-repeatable action. On recovery, verify actual state
and continue only the first incomplete step. If archive-to-final changes include
business code, Audit PASS is invalid and the workflow returns to `AUDITING`.
