# OpenSpec Dev Team Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable Codex-native OpenSpec development team with one main-session Orchestrator, five fixed-model custom agents, durable artifact handoffs, guarded publishing, and project symlink bootstrap.

**Architecture:** A portable `openspec-dev-team` skill instructs the current Codex session to route a serial OpenSpec state machine. Five native custom-agent TOML files perform specialized work in fresh contexts; one Python standard-library CLI validates state, digests, attempts, and publish receipts. Two small shell scripts install project links and diagnose global/project configuration.

**Tech Stack:** Markdown Agent Skills, Codex custom-agent TOML, Python 3 standard library, POSIX-compatible shell, `unittest`, Git, OpenSpec CLI.

**Spec:** `docs/superpowers/specs/2026-09-05-openspec-dev-team-design.md`

## Global Constraints

- Work directly on `main`; do not create a branch or worktree.
- OpenSpec remains the only lifecycle and implementation source of truth.
- The current Codex session is the Orchestrator and does not have a forced model.
- The five specialist agents must declare exact model and reasoning values from the design.
- Do not add runtime dependencies beyond Python 3, shell, Git, and OpenSpec.
- Do not hard-code `openspec/changes/<change>`; consume paths returned by OpenSpec JSON.
- Runtime state and handoffs live under project `.agents/state/` and `.agents/runs/` and remain uncommitted.
- Use explicit Git file allowlists; never use `git add .`, `git add -A`, force-push, reset, clean, or history rewriting.
- Pi and Claude Code are documentation-only mappings in the first release.
- Vela verification is read-only and must not modify or push `/Users/kaden/Vela`.

## File Map

- `agents/shared/workflow-policy.md`: lifecycle invariants, Human Gate, retry, Git, and token rules.
- `agents/shared/handoff-contract.md`: handoff fields, stage requirements, digest rules, and stale-attempt rejection.
- `agents/team/*.md`: one concise responsibility contract for the Orchestrator and each specialist.
- `skills/openspec-dev-team/SKILL.md`: user entry point and Orchestrator routing instructions.
- `skills/openspec-dev-team/references/state-machine.md`: event table and publishing recovery sequence.
- `profiles/codex/agents/*.toml`: five native Codex custom-agent definitions.
- `profiles/codex/model-map.md`: exact models plus tool/MCP capability mapping and enforcement limits.
- `profiles/pi/README.md`, `profiles/claude-code/README.md`: template-only platform mappings.
- `templates/project.md`: per-project configuration contract.
- `scripts/workflow-state.py`: deterministic JSON state, handoff, digest, approval, and publish-receipt CLI.
- `scripts/link-project.sh`: idempotent project bootstrap with dry-run and no overwrite.
- `scripts/doctor.sh`: global/project diagnostics without credential output.
- `tests/test_contracts.py`: static contract and profile checks.
- `tests/test_workflow_state.py`: state/digest/recovery behavior.
- `tests/test_link_project.py`: symlink bootstrap behavior.
- `tests/test_doctor.py`: diagnostic behavior with isolated fixtures.

---

### Task 1: Workflow and Role Contracts

**Files:**
- Create: `agents/shared/workflow-policy.md`
- Create: `agents/shared/handoff-contract.md`
- Create: `agents/team/orchestrator.md`
- Create: `agents/team/explore-proposal.md`
- Create: `agents/team/proposal-reviewer.md`
- Create: `agents/team/apply-executor.md`
- Create: `agents/team/pre-archive-auditor.md`
- Create: `agents/team/archivist-publisher.md`
- Create: `skills/openspec-dev-team/references/state-machine.md`
- Create: `tests/test_contracts.py`

**Interfaces:**
- Consumes: approved design document.
- Produces: canonical state names, events, role ownership, handoff fields, digest semantics, and permission boundaries used by every later task.

- [ ] **Step 1: Write failing contract tests**

Create `tests/test_contracts.py` with `unittest`. Assert that all nine contract files exist; every role file contains `READ`, `WRITE`, `FORBIDDEN`, `INPUT`, and `OUTPUT`; `state-machine.md` contains every state/event pair from the design; and `handoff-contract.md` contains these exact fields:

```python
REQUIRED_HANDOFF_FIELDS = {
    "RUN_ID", "ATTEMPT_ID", "STATUS", "CHANGE",
    "REQUEST_ARTIFACT", "APPROVAL_ARTIFACT", "SUMMARY",
    "EVIDENCE", "BLOCKERS", "ARTIFACTS", "PROPOSAL_DIGEST",
    "PROGRESS_DIGEST", "BASE_SHA", "HEAD_SHA",
    "PUBLISH_STEP_RECEIPTS", "NEXT_STATE",
}
```

Also assert that `workflow-policy.md` contains `OpenSpec`, `Human Gate`, `main`, and the prohibited Git commands.

- [ ] **Step 2: Run the tests and confirm the missing-file failure**

Run: `python3 tests/test_contracts.py -v`

Expected: FAIL because the contract files do not exist.

- [ ] **Step 3: Write the minimum canonical contracts**

Create the files listed above. Keep each role file limited to purpose, phase-specific inputs, allowed reads/writes, forbidden actions, required output, and escalation conditions. Put the full state + event table only in `state-machine.md`; role files link to it instead of repeating it.

`handoff-contract.md` must define:

```text
STATUS = PASS | FAIL | BLOCKED | NEEDS_HUMAN
CHANGE = null before OpenSpec Change creation
PROPOSAL_DIGEST = apply inputs with task checkboxes normalized
PROGRESS_DIGEST = exact task artifact
```

It must reject wrong `RUN_ID`, stale `ATTEMPT_ID`, unexpected owner, missing stage fields, illegal `NEXT_STATE`, and digest/SHA mismatch.

- [ ] **Step 4: Run the contract tests**

Run: `python3 tests/test_contracts.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the contracts**

```bash
git add agents/shared agents/team skills/openspec-dev-team/references/state-machine.md tests/test_contracts.py
git commit -m "docs: define OpenSpec team contracts"
```

### Task 2: Codex Custom Agents and Platform Mappings

**Files:**
- Create: `profiles/codex/agents/openspec-explore-proposal.toml`
- Create: `profiles/codex/agents/openspec-proposal-reviewer.toml`
- Create: `profiles/codex/agents/openspec-apply-executor.toml`
- Create: `profiles/codex/agents/openspec-pre-archive-auditor.toml`
- Create: `profiles/codex/agents/openspec-archivist-publisher.toml`
- Create: `profiles/codex/model-map.md`
- Create: `profiles/pi/README.md`
- Create: `profiles/claude-code/README.md`
- Modify: `tests/test_contracts.py`

**Interfaces:**
- Consumes: role markdown paths and permission contracts from Task 1.
- Produces: five Codex agent names that `SKILL.md` will request verbatim.

- [ ] **Step 1: Add failing TOML profile tests**

Extend `tests/test_contracts.py` using `tomllib`. Assert exact `(model, model_reasoning_effort, sandbox_mode)` tuples:

```python
EXPECTED_AGENTS = {
    "openspec-explore-proposal": ("gpt-5.6-sol", "medium", "workspace-write"),
    "openspec-proposal-reviewer": ("gpt-5.6-terra", "high", "read-only"),
    "openspec-apply-executor": ("gpt-5.6-terra", "high", "workspace-write"),
    "openspec-pre-archive-auditor": ("gpt-5.6-terra", "high", "workspace-write"),
    "openspec-archivist-publisher": ("gpt-5.6-luna", "medium", "workspace-write"),
}
```

Assert each TOML has `name`, `description`, and `developer_instructions`, and that the instructions reference the corresponding `agents/team/*.md` contract. Assert Pi and Claude Code documents contain `template-only` and do not claim end-to-end validation.

- [ ] **Step 2: Run the profile tests and confirm failure**

Run: `python3 tests/test_contracts.py -v`

Expected: FAIL because profile files are absent.

- [ ] **Step 3: Create the five native Codex agent definitions**

Use standalone TOML files compatible with `~/.codex/agents/`. Each file declares its exact name, model, reasoning, sandbox, and concise developer instructions. The instructions must tell the agent to read the shared contracts, its role contract, `.agents/project.md`, and only the artifact paths supplied in the spawn prompt.

Do not hard-code GitHub or Linear server names. In `model-map.md`, map logical READ/WRITE capabilities to parent-session MCP tools when configured, state that missing required capability produces `BLOCKED`, and state that sandbox inheritance is not process-level tool isolation.

- [ ] **Step 4: Write template-only Pi and Claude Code mappings**

For each platform, document discovery locations, fresh-context equivalent, model/tool fields requiring user mapping, and why this serial pipeline should use subagents rather than a shared Agent Team. Keep each file under 100 lines.

- [ ] **Step 5: Run the profile tests**

Run: `python3 tests/test_contracts.py -v`

Expected: PASS.

- [ ] **Step 6: Commit the platform profiles**

```bash
git add profiles tests/test_contracts.py
git commit -m "feat: define Codex specialist agents"
```

### Task 3: Deterministic Workflow State CLI

**Files:**
- Create: `scripts/workflow-state.py`
- Create: `tests/test_workflow_state.py`

**Interfaces:**
- Consumes: state/event and handoff contracts from Task 1.
- Produces CLI commands `init`, `approve`, `validate-handoff`, `transition`, `digest`, and `publish-receipt`; all successful mutation commands atomically rewrite one state JSON file.

- [ ] **Step 1: Write failing state transition tests**

Create subprocess-based `unittest` cases for:

```text
NEW + START -> EXPLORING
AWAITING_EXPLORE_APPROVAL + REJECT -> CANCELLED
REVIEWING_PROPOSAL + FAIL attempts 1/2 -> REVISING_PROPOSAL
REVIEWING_PROPOSAL + FAIL attempt 3 -> NEEDS_HUMAN
AUDITING + PASS without authorization -> READY_TO_PUBLISH
AUDITING + PASS with authorization -> PUBLISHING
BLOCKED + RESOLVED -> saved resume_state
```

Assert unknown events exit nonzero and leave the state file byte-for-byte unchanged.

- [ ] **Step 2: Run the transition tests and confirm failure**

Run: `python3 tests/test_workflow_state.py -v`

Expected: FAIL because `scripts/workflow-state.py` is absent.

- [ ] **Step 3: Implement state initialization and atomic transitions**

Use `argparse`, `json`, `hashlib`, `pathlib`, `tempfile`, `os.replace`, `subprocess`, `uuid`, and `datetime` only. `init` accepts `--project`, `--request`, optional `--source`, and `--publish`; it creates `.agents/state/<run-id>.json`, `.agents/runs/<run-id>/request.md`, captures project realpath, branch, remote URL, `BASE_SHA`, and non-ignored untracked baseline, and starts at `NEW`.

Represent attempts as UUID strings. Every specialist dispatch starts a new `ATTEMPT_ID`. Preserve `resume_state` when entering `BLOCKED`.

- [ ] **Step 4: Add failing handoff validation tests**

Cover valid pre-Change `CHANGE: null`, valid post-Apply fields, wrong run, stale attempt, wrong owner, missing required stage field, illegal next state, and invalid status. Assert invalid payloads never update state.

- [ ] **Step 5: Implement stage-aware handoff validation**

Use one `REQUIRED_BY_STATE` mapping and one `OWNER_BY_STATE` mapping. Return validation errors as concise JSON on stderr and exit nonzero. `transition --handoff <path>` first validates the payload, then applies the event and writes state atomically.

- [ ] **Step 6: Add failing digest tests**

Create fixture proposal/design/spec/tasks files. Assert changing only `- [ ]` to `- [x]` preserves `PROPOSAL_DIGEST` but changes `PROGRESS_DIGEST`; changing task text or design content changes `PROPOSAL_DIGEST`.

- [ ] **Step 7: Implement deterministic digests**

`digest` accepts repeated `--input PATH` and exactly one `--tasks PATH`. Sort resolved paths, include relative path names in the hash, normalize only Markdown checkbox marks for the proposal digest, and hash the task file unmodified for the progress digest. Print both values as JSON.

- [ ] **Step 8: Add failing approval and publish-receipt tests**

Assert approval stores decision, Explore digest, project realpath, branch, remote, authorization, and timestamp. Assert receipts append in the fixed step order, reject skipped/duplicate inconsistent steps, and allow an identical receipt to be replayed idempotently.

- [ ] **Step 9: Implement approval and publishing receipts**

`approve` verifies the Explore artifact digest before writing `approval.json`. `publish-receipt` accepts `--step`, `--result-file`, and optional `--archive-digest`/`--final-sha`; it records the receipt immediately and never deletes prior receipts.

- [ ] **Step 10: Run state tests and the complete suite**

Run:

```bash
python3 tests/test_workflow_state.py -v
python3 -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 11: Commit the state CLI**

```bash
git add scripts/workflow-state.py tests/test_workflow_state.py
git commit -m "feat: add guarded workflow state engine"
```

### Task 4: Project Bootstrap Script and Template

**Files:**
- Create: `templates/project.md`
- Create: `scripts/link-project.sh`
- Create: `tests/test_link_project.py`

**Interfaces:**
- Consumes: repository locations `agents/shared`, `agents/team`, and `templates/project.md`.
- Produces: project `.agents/` links, local config, ignored runtime directories, and no unrelated changes.

- [ ] **Step 1: Write failing bootstrap tests**

Use `tempfile.TemporaryDirectory` and subprocess calls. Cover `--dry-run`, first install, idempotent second install, preservation of an existing `project.md`, refusal to replace a regular `shared` directory, refusal to replace a wrong symlink, and exact `.agents/.gitignore` entries:

```text
/state/
/runs/
/*.lock
```

- [ ] **Step 2: Run bootstrap tests and confirm failure**

Run: `python3 tests/test_link_project.py -v`

Expected: FAIL because the script and template are absent.

- [ ] **Step 3: Create the project template**

Define exact fields for project name, project realpath, main branch, expected remote, stack, OpenSpec root selection, quality gates, protected data, project constraints, project skills, and optional Linear issue mapping. Use Markdown headings and fenced YAML examples; do not prescribe a second lifecycle.

- [ ] **Step 4: Implement the minimal idempotent shell script**

Accept `--dry-run` and one explicit project path. Resolve the script directory without relying on the caller's cwd. Validate the target is a Git repo before changes. Create `.agents`, correct relative-or-absolute symlinks to the two shared directories, copy the template only when absent, create runtime directories, and write only the three ignore entries above. Refuse all conflicting existing paths.

- [ ] **Step 5: Run bootstrap tests**

Run: `python3 tests/test_link_project.py -v`

Expected: PASS.

- [ ] **Step 6: Commit bootstrap files**

```bash
git add templates/project.md scripts/link-project.sh tests/test_link_project.py
git commit -m "feat: add project bootstrap"
```

### Task 5: Global and Project Doctor

**Files:**
- Create: `scripts/doctor.sh`
- Create: `tests/test_doctor.py`

**Interfaces:**
- Consumes: installed skill/agent links, project template contract, Git, OpenSpec CLI, and workflow state files.
- Produces: line-oriented `PASS`, `WARN`, or `FAIL` diagnostics with no credential values.

- [ ] **Step 1: Write failing doctor tests**

Build isolated fake Home and Git project fixtures. Place fake `git`, `openspec`, and `python3` executables first on `PATH` where deterministic output is required. Cover:

```text
--global: correct links and five exact agent models -> exit 0
--global: missing skill link -> nonzero
--project: correct OpenSpec root and project.md -> exit 0
--project: tracked dirty or staged files -> NEEDS_HUMAN diagnostic
--project: untracked baseline only -> no failure
--project: stale lock -> warning
```

Assert output never includes environment variables containing `TOKEN`, `KEY`, or `SECRET`.

- [ ] **Step 2: Run doctor tests and confirm failure**

Run: `python3 tests/test_doctor.py -v`

Expected: FAIL because `scripts/doctor.sh` is absent.

- [ ] **Step 3: Implement `doctor.sh --global`**

Check `git`, `openspec`, and `python3`; the skill symlink target; five agent symlink targets; required TOML keys; exact model/reasoning values; executable scripts; and template-only labels. Print capability presence only, never MCP configuration bodies or credentials.

- [ ] **Step 4: Implement `doctor.sh --project PATH`**

Resolve Git root and nearest OpenSpec root, run `openspec list --json` and `openspec doctor`, validate `.agents` links and `project.md` fields, use `git check-ignore` for runtime paths, detect tracked/index dirtiness, list only path names for non-ignored untracked files, and identify locks whose recorded process/session is absent.

- [ ] **Step 5: Run doctor tests and complete suite**

Run:

```bash
python3 tests/test_doctor.py -v
python3 -m unittest discover -s tests -v
```

Expected: PASS.

- [ ] **Step 6: Commit the doctor**

```bash
git add scripts/doctor.sh tests/test_doctor.py
git commit -m "feat: add workflow diagnostics"
```

### Task 6: Orchestration Skill and User Documentation

**Files:**
- Create: `skills/openspec-dev-team/SKILL.md`
- Create: `README.md`
- Modify: `tests/test_contracts.py`

**Interfaces:**
- Consumes: five exact custom-agent names, state CLI commands, contracts, and `.agents/project.md`.
- Produces: `$openspec-dev-team` entry behavior for new runs, Human Gate continuation, recovery, and dry smoke dispatch.

- [ ] **Step 1: Add failing skill tests**

Assert `SKILL.md` frontmatter has `name: openspec-dev-team` and a description that triggers on OpenSpec team workflow requests. Assert its body names all five agents, requires fresh context, reads `REQUEST_ARTIFACT`, validates every handoff through `workflow-state.py`, pauses at `AWAITING_EXPLORE_APPROVAL`, treats `PUBLISHING` as receipt-based recovery, and never instructs the Orchestrator to implement/review/publish directly.

- [ ] **Step 2: Run contract tests and confirm failure**

Run: `python3 tests/test_contracts.py -v`

Expected: FAIL because `SKILL.md` and `README.md` are absent.

- [ ] **Step 3: Write the concise orchestration skill**

Keep `SKILL.md` under 220 lines. Its algorithm is:

```text
discover project -> run doctor -> init/resume state -> resolve owner
-> spawn named custom agent with fresh context -> validate/persist handoff
-> transition -> stop only at Human Gate, terminal state, or blocker
```

For Propose/Apply, instruct agents to use `openspec status` and `openspec instructions` paths. For review/audit, provide only the Change inputs, direct code paths, or `BASE..HEAD` diff. For publishing, require reconciliation of actual Git/OpenSpec/Linear state before recording or continuing each receipt.

Define `$openspec-dev-team smoke` as a no-write diagnostic path that sequentially dispatches all five named agents against supplied fixture artifacts, validates current-attempt handoffs, deliberately checks stale-attempt rejection, and requires Publisher to stop at unauthorized preflight.

- [ ] **Step 4: Write README installation and usage**

Document the project purpose, prerequisites, one-time skill/agent symlinks, project bootstrap, `$openspec-dev-team <request> [--publish]`, Human Gate continuation, `doctor` commands, model map, and removal of symlinks. State that custom-agent discovery may require starting a new Codex session.

- [ ] **Step 5: Run all automated tests**

Run:

```bash
python3 -m unittest discover -s tests -v
git diff --check
```

Expected: PASS.

- [ ] **Step 6: Commit the skill and README**

```bash
git add skills/openspec-dev-team/SKILL.md README.md tests/test_contracts.py
git commit -m "feat: add OpenSpec team orchestration skill"
```

### Task 7: Install and Verify the Complete Workflow

**Files:**
- Modify only if verification reveals a defect: files owned by Tasks 1-6 and their corresponding tests.
- Do not modify: `/Users/kaden/Vela/**`.

**Interfaces:**
- Consumes: completed repository, clean `main`, local Codex CLI 0.153.4 or newer, and ChatGPT-authenticated Codex.
- Produces: installed symlinks plus fresh automated, real-dispatch, and Vela read-only evidence.

- [ ] **Step 1: Run the complete automated gate**

Run:

```bash
python3 -m unittest discover -s tests -v
git diff --check
git status --short
```

Expected: all tests pass, no whitespace errors, and no unexpected changes.

- [ ] **Step 2: Install the global Codex links**

Resolve and verify each source before linking. Create only these links, refusing to replace conflicting paths:

```text
~/.codex/skills/openspec-dev-team
~/.codex/agents/openspec-explore-proposal.toml
~/.codex/agents/openspec-proposal-reviewer.toml
~/.codex/agents/openspec-apply-executor.toml
~/.codex/agents/openspec-pre-archive-auditor.toml
~/.codex/agents/openspec-archivist-publisher.toml
```

- [ ] **Step 3: Run global doctor**

Run: `scripts/doctor.sh --global`

Expected: PASS for the skill, five agents, explicit models/reasoning, Git, OpenSpec, and Python.

- [ ] **Step 4: Run a real custom-agent dispatch smoke test in a temporary project**

Create a temporary Git/OpenSpec fixture with `.agents/project.md` and a request artifact that asks each role only to identify its role and return a valid no-write handoff. From a fresh Codex session, invoke `$openspec-dev-team` in smoke mode. Require five sequential native custom-agent dispatches with fresh context and unique `ATTEMPT_ID` values. Verify the Orchestrator rejects one intentionally stale fixture handoff, accepts each current handoff, and asks the Publisher to perform only unauthorized preflight; Publisher must return refusal without archive, commit, push, or Linear write.

Capture only command, exit status, agent names, attempt ids, and artifact paths under the temporary project's `.agents/runs/`; do not commit smoke evidence.

- [ ] **Step 5: Run the Vela read-only smoke test**

Before and after the test, capture:

```bash
git -C /Users/kaden/Vela status --porcelain=v1
git -C /Users/kaden/Vela rev-parse HEAD
```

Run: `scripts/doctor.sh --project /Users/kaden/Vela`

Expected: detect `main`, the nearest OpenSpec root, quality-gate instructions, zero active changes, and existing untracked database sidecars without changing either status output or HEAD.

- [ ] **Step 6: Re-run verification after smoke tests**

Run:

```bash
python3 -m unittest discover -s tests -v
scripts/doctor.sh --global
git diff --check
git status --short --branch
```

Expected: all checks pass and repository `main` is clean. If verification required a source fix, add a focused regression test, commit only that fix and test, and repeat this step.
