## Context

See `proposal.md` for the observed discovery failure and motivation. The
current installation example creates symlinks for the five files under
`$HOME/.codex/agents`, and `scripts/doctor.sh` requires those symlinks. A
controlled `codex-cli 0.154.0` A/B run showed that built-in discovery works and
all five custom roles dispatch with regular profile files, while the first
custom role is unavailable when only the profiles are symlinked. The skill
symlink and project `.agents/shared` link are separate cross-project links and
are not part of this compatibility fix.

## Goals / Non-Goals

**Goals:**

- Install the five native Agent TOMLs as readable regular files that match the
  repository source at installation time.
- Make global diagnostics detect missing, symlinked, malformed, or
  source-drifting profile copies.
- Provide safe, explicit handling for existing symlinks and regular files.
- Verify native discovery and no-write workflow behavior in a fresh temporary
  Codex session.
- Make the unauthorized Publisher preflight handoff explicitly emit the fields
  already required by the validator: `STATUS=BLOCKED`,
  `PUBLISH_STEP=PREFLIGHT`, `NEXT_STATE=BLOCKED`,
  `PUBLISH_STEP_RECEIPTS=[]`, and `ARCHIVE_DIGEST=null`.

**Non-Goals:**

- Do not change the five TOML role contracts, Agent names, models, or sandbox
  modes.
- Do not change the skill symlink, `.agents/shared` project link, workflow state
  machine routing, or the current consolidation Change. The Publisher and
  reference wording only makes the existing blocked-handoff contract explicit.
- Do not patch Codex, add a runtime dependency, or assume an unverified
  `config.toml` workaround.
- Do not automatically edit a user’s real Codex home or remove an unowned
  destination.

## Decisions

### 1. Copy profiles; keep the source repository authoritative

The installation instructions will copy each file from
`profiles/codex/agents/` into `$HOME/.codex/agents/` instead of creating a
profile symlink. The repository remains the single authored source; the
installed files are a generated deployment copy refreshed by rerunning the
installation instructions.

Keeping symlinks is rejected because the native router rejects the exact
custom type even when the link target is correct. An explicit Codex
`config.toml` registry is not selected because it would add per-user config
state and has not been behaviorally verified. Waiting for a future Codex fix
does not provide a working installation now.

### 2. Refuse implicit replacement and detect source drift

Installation will preflight every destination and refuse any existing file,
directory, or symlink rather than overwrite it. The instructions will tell the
user to verify and remove an old installation explicitly before retrying.

Diagnostics will require a non-symlink regular file, parse the installed TOML,
check the exact filename/name and documented metadata, and compare its bytes
with the repository profile. This catches both accidental edits and stale
copies without introducing a manifest format.

### 3. Make removal ownership-aware

Removal will delete a regular profile only when its bytes still match the
repository source. It will preserve source-drifting files and symlinks to
other targets, reporting the path for manual review. Existing symlink cleanup
for the skill and shared project contract remains guarded by target checks.

### 4. Make the blocked handoff contract explicit

The Publisher profile, handoff contract, state-machine publishing reference,
and smoke instructions will use the same exact unauthorized preflight fields.
This aligns the role output with `validate_handoff`, which already routes a
`BLOCKED` event from `PUBLISHING` to `BLOCKED` and preserves `PUBLISHING` as
`RESUME_STATE`.

### 5. Verify the behavior at the native boundary

The compatibility smoke will use a fresh temporary `CODEX_HOME` populated with
the skill link and regular profile copies, record the Codex version, and run a
fresh `codex exec --ephemeral --sandbox read-only --ignore-user-config` session
(or an equivalent native fresh-session invocation) against a disposable fixture
project. The fixture is snapshotted before and after the run; because specialist
profiles include workspace-write modes, any attempted write or changed
fixture/project path is a failure rather than something inferred from parent
sandbox inheritance. The smoke will dispatch the five exact Agent names
serially with fresh context, validate each current handoff, reject copied stale
`ATTEMPT_ID` values, and require unauthorized Publisher `PREFLIGHT` to return
the explicit blocked handoff. Dispatch transcripts and validation results are
captured outside the repository, and the smoke never runs lifecycle or external
publication actions.

### 6. Isolate this Change from parallel consolidation work

The currently active `consolidate-codex-agent-definitions` Change touches several
of the same documentation, contract, profile, and test paths. This Change is
applied only after that shared-file work has a stable reviewed revision, or
under an explicitly reviewed combined scope; it must not silently absorb or
stage consolidation-only edits. If the baseline or ownership of a shared edit
cannot be established, stop for a Human Gate instead of combining the Changes.

## Risks / Trade-offs

- [Source edits no longer appear immediately in the installed copy] → State
  the refresh step prominently and have diagnostics identify source drift.
- [Existing symlink installations will initially conflict] → Keep preflight
  fail-closed and document target-verified removal before reinstalling.
- [A user can edit an installed copy] → Byte comparison and TOML/metadata
  checks report the drift without deleting the user’s file.
- [Byte equality cannot prove file provenance] → Treat `cmp` as a content-based
  ownership check; document that an uncertain identical file must be handled
  manually, and do not introduce a manifest for this MVP.
- [A later Codex release may add symlink support] → Regular files remain a
  valid native layout; any future reversion can be proposed separately with
  fresh native evidence.

## Migration Plan

1. Update the installation and diagnostic contracts and their focused tests.
2. For an existing installation, verify old profile symlink targets and remove
   only links owned by this checkout using the documented guarded procedure;
   because ownership is content-based for regular files, route uncertain
   identical files to manual review.
3. Re-run installation to create regular profile copies, then run the global
   diagnostic and start a new Codex session.
4. Run the no-write native smoke. If rollback is needed, remove only matching
   regular copies; leave drifted or unowned destinations for manual review.
