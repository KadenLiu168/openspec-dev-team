---
name: openspec-dev-team
description: Use when coordinating an OpenSpec development team workflow from exploration through optional publication.
---

# OpenSpec Development Team

## Purpose

Coordinate the serial OpenSpec team workflow. OpenSpec is the sole lifecycle
and implementation source of truth; this skill adds mechanical routing, a Human
Gate, validated handoffs, and recovery, not a parallel lifecycle.
The Orchestrator owns request provenance, serial dispatch, handoff persistence,
and escalation. The Orchestrator must not implement, review, or publish; it never
receives the full conversation or substitutes itself for a specialist.

Resolve three roots before routing. `SKILL_DIR` is the concrete directory that
contains this `SKILL.md` after resolving an installed symlink; `TEAM_ROOT` is two
directories above `SKILL_DIR`; `PROJECT_ROOT` is the target project's Git root.
The `python3` resolved from `PATH` must be Python 3.11+ with `tomllib`.

Load canonical references operation-specific, not all at startup. Read only
the sections needed for the current operation:

- `$SKILL_DIR/references/state-machine.md` is the canonical reference for routing and transition decisions.
- `$TEAM_ROOT/agents/shared/workflow-policy.md` is the canonical reference for workflow-boundary checks.
- `$TEAM_ROOT/agents/shared/handoff-contract.md` is the canonical reference for handoff validation.
- Load `$PROJECT_ROOT/.agents/project.md` before project-bound operations.

The Orchestrator writes only request/approval/run evidence and accepted handoffs under `.agents`.
Escalate Human Gates, invalid scope, third blocking findings, dirty tracked state,
unresolved blockers, ambiguous owners, or illegal transitions instead of guessing.
Work serially on `main`; never create a branch or worktree, and never hard-code an
OpenSpec Change directory.

## Owner map

| Canonical owner | Native custom agent |
| --- | --- |
| Explore / Proposal | `openspec-explore-proposal` |
| Proposal Reviewer | `openspec-proposal-reviewer` |
| Apply Executor | `openspec-apply-executor` |
| Pre-Archive Auditor | `openspec-pre-archive-auditor` |
| Archivist / Publisher | `openspec-archivist-publisher` |

Dispatch only the expected owner for the current state. Each dispatch is a
fresh context containing only contract fields and bounded artifact paths.

## Start or resume

1. Discover `PROJECT_ROOT` and read `$PROJECT_ROOT/.agents/project.md`. Require its
   `PROJECT_REALPATH`, `main` branch, and remote bindings to match reality.
2. Run `"$TEAM_ROOT/scripts/doctor.sh" --global` and
   `"$TEAM_ROOT/scripts/doctor.sh" --project "$PROJECT_REALPATH"`. Stop on
   failure; dirty tracked or staged state is `NEEDS_HUMAN`.
3. For a new request, run:

   ```text
   python3 "$TEAM_ROOT/scripts/workflow-state.py" init --project "$PROJECT_ROOT" --request "$REQUEST" [--publish]
   ```

   This creates `REQUEST_ARTIFACT`, `.agents/state/<RUN_ID>.json`, and
   `.agents/runs/<RUN_ID>/`, binding `BASE_SHA`, `UNTRACKED_BASELINE`, `BRANCH`,
   `REMOTE_URL`, and project provenance before Explore. Treat `--publish` as
   intent, never authorization.
4. To resume, select the explicit run-id, read its existing state file, verify
   the saved project and request provenance, and continue from its saved state.
   Never initialize a replacement run. `DONE` and `CANCELLED` are terminal.
   Before re-dispatching an interrupted normal specialist stage, run
   `python3 "$TEAM_ROOT/scripts/workflow-state.py" dispatch --state <state>`.
   It atomically issues a new `ATTEMPT_ID`; old handoffs become stale. Read the
   returned state and spawn fresh context. Do not use it for gates, blockers,
   or `PUBLISHING`, which requires receipt reconciliation.
5. From `NEW`, use `python3 "$TEAM_ROOT/scripts/workflow-state.py" transition
   --state <state> --event START`. Then resolve the current state and expected
   owner from the canonical table.

## Dispatch inputs

Every specialist receives `PROJECT_ROOT`, current `RUN_ID`, `ATTEMPT_ID`, owner, state,
expected output/`NEXT_STATE`, `REQUEST_ARTIFACT`, applicable
`APPROVAL_ARTIFACT` and `APPROVAL_DIGEST`, bindings, and only these phase inputs:

- `EXPLORING`: Read `REQUEST_ARTIFACT` and the minimal artifact inputs needed
  to produce an Explore Result; make no project writes.
- `PROPOSING` or `REVISING_PROPOSAL`: use `openspec status --change <name>
  --json` and `openspec instructions apply --change <name> --json`. Derive
  `planningHome`, `changeRoot`, `artifactPaths`, and `actionContext` from their
  output. Supply the approved Explore Result and those paths only.
- `REVIEWING_PROPOSAL`: supply approved Explore Result and Change inputs only;
  request structured Review Findings.
- `APPLYING` or `FIXING_IMPLEMENTATION`: supply approved Change inputs,
  applicable findings, quality gates, and direct code paths from the OpenSpec
  action context. Include current reviewed Change artifact paths in the local
  commit allowlist alongside implementation and tests; commit them before Audit.
- `AUDITING`: supply approved Change inputs, implementation handoff, direct
  code paths, and the `BASE..HEAD` diff; request fresh Audit Findings.
- `PUBLISHING`: supply authorization, Audit bindings, current receipts, and the
  next verified publish step only.

Compute proposal and progress bindings with repeated `--input` values and
exactly one tasks file:

```text
python3 "$TEAM_ROOT/scripts/workflow-state.py" digest --input <proposal> --input <design-or-spec> --tasks <tasks>
```

Carry `PROPOSAL_DIGEST` and `PROGRESS_DIGEST` through later handoffs. Proposal/revision may produce new
proposal/progress digests; Apply/fix may produce new progress and `HEAD_SHA`.
Review binds its current proposal, and Audit/Publisher bind all audited inputs.

## Accept, persist, and route

For every returned handoff, require all contract fields, including `RUN_ID`,
current `ATTEMPT_ID`, `OWNER`, `NEXT_STATE`, bindings, and evidence. Stage the
candidate outside runtime state, then run:

```text
python3 "$TEAM_ROOT/scripts/workflow-state.py" validate-handoff --state <state> --handoff <candidate> --event <event>
python3 "$TEAM_ROOT/scripts/workflow-state.py" transition --state <state> --event <event> --handoff <candidate>
```

The second command revalidates, persists the accepted handoff, and updates
state atomically. A rejected handoff is not persisted and leaves state
unchanged; report `BLOCKED` with validation evidence instead of guessing or
dispatching another owner. Never accept a stale attempt. For `STEP_PASS`, use
the three-command sequence in the Publishing reference below instead.
For `PROPOSAL_CHANGED`, use `STATUS=PASS` and require `SCOPE` to be
`WITHIN_APPROVED_SCOPE` or `OUTSIDE_APPROVED_SCOPE`; the latter invalidates
approval and returns to Explore. `NEEDS_HUMAN` uses the same event and status,
saves `RESUME_STATE`, and follows this same validate-then-transition path.

Continue the serial loop until a Human Gate, terminal state, `BLOCKED`, or
`NEEDS_HUMAN`. `BLOCKED` never retries automatically. Resume only with new
evidence proving the blocker removed:

```text
python3 "$TEAM_ROOT/scripts/workflow-state.py" transition --state <state> --event RESOLVED --evidence <file>
```

Use `RESOLVE_BLOCKER` from `NEEDS_HUMAN`; both restore only validated
`RESUME_STATE`.

## Human Gate

Always pause at `AWAITING_EXPLORE_APPROVAL` and present the saved Explore Result
at the Human Gate. Record the decision before routing:

```text
python3 "$TEAM_ROOT/scripts/workflow-state.py" approve --state <state> --explore-result <file> --decision APPROVE [--publish-authorized]
python3 "$TEAM_ROOT/scripts/workflow-state.py" approve --state <state> --explore-result <file> --decision REVISE
python3 "$TEAM_ROOT/scripts/workflow-state.py" approve --state <state> --explore-result <file> --decision REJECT
```

Apply the matching transition. `APPROVAL_ARTIFACT` binds `EXPLORE_DIGEST`,
project, branch, remote, and publish scope. With `--publish-authorized`,
`approve` also persists `PUBLISH_AUTHORIZATION` bound to `UNTRACKED_BASELINE`
(which may be `[]`); Audit PASS completes and validates it before `PUBLISHING`.
Otherwise Audit PASS stops at `READY_TO_PUBLISH`.
For explicit later authorization there, preserve the original approval and run:

```text
python3 "$TEAM_ROOT/scripts/workflow-state.py" authorize-publish --state <state> --evidence <human-decision-file>
python3 "$TEAM_ROOT/scripts/workflow-state.py" transition --state <state> --event AUTHORIZE_PUBLISH
```

The first command persists `PUBLISH_AUTHORIZED` and a `PUBLISH_AUTHORIZATION`
record bound to the decision's project, approval, and Audit inputs before the
second enters `PUBLISHING`.

## Publishing and recovery

Only `openspec-archivist-publisher` may publish after explicit authorization
and valid Audit bindings. For `PUBLISHING` or publishing-specific handoff
validation, read [Publishing steps](references/state-machine.md#publishing-steps)
before taking the next step; earlier phases do not load that section.
That reference owns receipt reconciliation and the validate/record/transition
sequence. Invalid authorization or bindings are `BLOCKED`; continue only the
first incomplete verified step and never repeat a proven external effect.
Archive output containing business code invalidates Audit PASS and requires
`AUDITING` again.

## Smoke

`$openspec-dev-team smoke` is a no-write diagnostic. Before invoking it, prepare
a disposable fixture project and a fresh temporary `CODEX_HOME` containing the
skill symlink and five regular profile copies, then record `codex --version`.
Run a fresh `codex exec --ephemeral --sandbox read-only --ignore-user-config`
session (or an equivalent native fresh-session invocation) against that fixture.
Snapshot fixture/project paths before and after. Specialist profiles may request
`workspace-write`, so any attempted write or changed fixture/project path is a
failure; do not infer isolation from parent sandbox inheritance.
Populate `CODEX_HOME` with the skill symlink and `cp` copies of all five
`profiles/codex/agents/*.toml` before starting the session.

It uses supplied fixture artifacts and sequentially dispatches these five native
agents in fresh context:

1. `openspec-explore-proposal`
2. `openspec-proposal-reviewer`
3. `openspec-apply-executor`
4. `openspec-pre-archive-auditor`
5. `openspec-archivist-publisher`

Constrain every role to inspection and synthetic handoff generation. For each
fixture state, validate the current-attempt result with `validate-handoff` and
its exact `ATTEMPT_ID`. Then submit a copy with a stale ATTEMPT_ID: validation
must return nonzero and the fixture and project must remain unchanged. Dispatch
Publisher for unauthorized preflight only; it must return
`STATUS=BLOCKED`, `PUBLISH_STEP=PREFLIGHT`, `NEXT_STATE=BLOCKED`,
`PUBLISH_STEP_RECEIPTS=[]`, and `ARCHIVE_DIGEST=null`, then do not run archive,
commit, push, or Linear actions. Capture the dispatch transcript, validation
output, and stale-rejection result outside the repository.

Smoke must not mutate lifecycle or external state: do not run `init`, `approve`, `dispatch`, `authorize-publish`, `transition`, or `publish-receipt`; do not write artifacts, invoke OpenSpec archive, or allow any attempted write.
