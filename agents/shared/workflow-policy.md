# OpenSpec Team Workflow Policy

OpenSpec is the sole lifecycle and implementation source of truth. This team
uses its artifacts and CLI primitives; no role creates a parallel specification,
plan, state system, or full-conversation handoff.

## Routing and Human Gate

The Orchestrator owns mechanical routing and uses the canonical transitions in
[`state-machine.md`](../../skills/openspec-dev-team/references/state-machine.md).
It dispatches one expected owner with fresh context and only the contract input
fields. The workflow is serial.

There is one default active Human Gate: after Explore. The Orchestrator writes
request provenance before Explore, then records the human decision in an
approval artifact bound to the Explore Result digest, project realpath, branch,
remote, and publish authorization. Gate-time publish authorization also creates
a `PUBLISH_AUTHORIZATION` record bound to the untracked baseline; Audit PASS
completes its Change/digest/SHA fields and validates the saved scope before
routing directly to Publishing. Changing the result or that scope invalidates
the approval. Without authorization, a passing Audit stops at
`READY_TO_PUBLISH`.
Explicit later authorization may be recorded there with `authorize-publish`,
bound to the current project, approval digest, and audited inputs; it preserves
the original Human Gate artifact before the `AUTHORIZE_PUBLISH` transition.

## Project and Git Boundaries

All work occurs serially on project `main`; do not create a branch or worktree.
At run start, record `BASE_SHA` and the non-ignored untracked baseline. Staged
or tracked dirty changes require `NEEDS_HUMAN`. Pre-existing non-ignored
untracked files are preserved and never staged, deleted, or overwritten.

Apply owns the local commit of its implementation, tests, and the current
approved Change artifacts (proposal, design, delta specs, and tasks), using an
explicit file allowlist resolved from supplied OpenSpec status/instructions.
Recompute `PROPOSAL_DIGEST` and require it to match the latest Proposal Review
PASS before staging those artifacts; only task checkbox progress may differ.
Exclude baseline untracked files, unrelated changes, and runtime evidence.
Explore/Proposal and Reviewer never stage or commit. Apply does not push.
Before Audit, tracked worktree
and index must be clean and there must be no non-baseline non-ignored untracked
files. Publisher repeats those checks, along with branch, remote, Audit binding,
HEAD, and digests.

The following Git operations are prohibited: `git add .`, `git add -A`,
force-push, `reset`, `clean`, and history rewrite. Do not pull, merge, or
rebase to resolve a remote or `main` anomaly; return `BLOCKED` instead.

## OpenSpec Boundaries

`explore`, `propose`, and `apply` name workflow phases, not local OpenSpec CLI
subcommands. Use `openspec status --change <name> --json` as the source for
`planningHome`, `changeRoot`, `artifactPaths`, and `actionContext`; never
hard-code a change path. The relevant primitives are `openspec new change`,
`openspec status`, `openspec instructions apply`, strict validation, and
`openspec archive`.

## Runtime and Evidence

Runtime state is local and uncommitted under `.agents/state/<run-id>.json` and
`.agents/runs/<run-id>/`. It holds identifiers, routing data, SHAs, digests,
authorization scope, receipts, and artifact paths, but not requirement, design,
or implementation-plan bodies. The Orchestrator validates a handoff, persists
it, and atomically updates state. Evidence records command, exit code, time,
and log path only.

`BLOCKED` never retries automatically. It resumes only when the Orchestrator
has new evidence that validates the saved `resume_state`. Proposal review and
Audit each allow at most two automatic remediation rounds; a third blocking
finding routes to `NEEDS_HUMAN`.
An interrupted normal stage uses `dispatch --state` to persist a new
`ATTEMPT_ID` before fresh re-dispatch; prior attempts are stale. Publishing
resumes only through receipts, and blockers require resolution evidence.
