# codex-agent-installation Specification

## Purpose

Provide a safe, reproducible installation of the OpenSpec team’s native Codex
Agent profiles that Codex can discover and dispatch in a fresh session.

## Requirements

### Requirement: Install native profiles as regular files

The installation SHALL place exactly the five documented specialist TOMLs in
the native Codex Agent directory as readable, non-symlink regular files. Each
installed file SHALL retain its documented filename, embedded `name`, required
metadata, and role instructions, and SHALL match the corresponding repository
profile at installation time.

#### Scenario: Fresh installation creates discoverable profiles

- **WHEN** a user installs the team into an empty Codex home
- **THEN** all five documented profile paths exist as regular files and their
  contents match `profiles/codex/agents/`

#### Scenario: Existing destination is protected

- **WHEN** an installation destination already exists as a file or symlink
- **THEN** installation refuses that destination with an actionable conflict
  message and does not overwrite it implicitly

### Requirement: Diagnose installed profile integrity

The global diagnostic SHALL verify that every installed specialist profile is a
regular file whose filename, TOML `name`, required fields, documented
model/reasoning/sandbox values, and source-derived contents are valid. It SHALL
report a failure for a symlink, missing profile, malformed profile, or stale
contents.

#### Scenario: Symlinked profile is rejected

- **WHEN** an installed specialist path is a symlink, even if it targets the
  matching repository profile
- **THEN** the diagnostic reports that profile as invalid and explains that a
  regular file is required for native discovery

#### Scenario: Edited installed copy is rejected

- **WHEN** an installed regular file differs from its repository profile
- **THEN** the diagnostic reports source drift and identifies the profile that
  must be reinstalled

### Requirement: Remove installed profiles without deleting unrelated data

The removal guidance SHALL remove only an installation owned by this checkout.
It SHALL verify a regular installed profile matches its repository source before
deleting it, and SHALL refuse to delete a missing, symlinked-to-another-target,
or source-drifting destination implicitly.

#### Scenario: Matching regular installation is removed

- **WHEN** removal finds a regular installed profile whose contents match this
  checkout’s profile
- **THEN** it removes that profile and leaves unrelated files untouched

#### Scenario: Unowned or drifted destination is preserved

- **WHEN** removal finds a symlink to another target or a regular file with
  different contents
- **THEN** it refuses that path and preserves the destination

#### Scenario: Repository-owned legacy profile symlink is removed

- **WHEN** removal finds a profile symlink whose target is the corresponding
  profile in this checkout
- **THEN** it removes that symlink and does not remove any other destination

### Requirement: Native discovery remains behaviorally verified

The compatibility gate SHALL run in a fresh Codex session with the five regular
installed profiles and SHALL verify sequential native dispatch of all unchanged
Agent names. The gate SHALL use no-write fixtures, reject stale `ATTEMPT_ID`
handoffs, and require unauthorized Publisher preflight to return `BLOCKED`
without archive, commit, push, or external-record actions.

#### Scenario: All five profiles dispatch sequentially

- **WHEN** the compatibility gate runs with valid regular installed profiles
- **THEN** Explore, Proposal Reviewer, Apply Executor, Pre-Archive Auditor, and
  Archivist/Publisher dispatch in order with fresh context and exact native
  Agent names

#### Scenario: Unauthorized publication remains blocked

- **WHEN** the smoke reaches Archivist/Publisher without publish authorization
- **THEN** it returns `STATUS=BLOCKED`, `PUBLISH_STEP=PREFLIGHT`,
  `NEXT_STATE=BLOCKED`, `PUBLISH_STEP_RECEIPTS=[]`, and `ARCHIVE_DIGEST=null`,
  rejects a stale attempt, and performs no lifecycle or external write

#### Scenario: Invalid blocked preflight digest is rejected

- **WHEN** an unauthorized Publisher preflight handoff omits
  `ARCHIVE_DIGEST` or provides a non-null value
- **THEN** handoff validation fails without changing lifecycle state or receipt
  state
