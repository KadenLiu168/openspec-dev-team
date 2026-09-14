## Why

The documented installation creates symlinks for the five custom Codex Agent
TOMLs, but Codex 0.154.0 cannot discover those symlinked profiles through the
native `spawn_agent` tool. A controlled smoke run succeeds when the same TOMLs
are regular files, while a built-in Agent still works with symlinked profiles;
this leaves the current Change's native-discovery acceptance blocked.

## What Changes

- **BREAKING** Change the documented global installation of the five Codex
  Agent TOMLs from symlinks to regular files copied from
  `profiles/codex/agents/`.
- Update diagnostics to validate regular installed files, their exact Agent
  names, required fields, and source-derived contents without requiring
  symlink identity.
- Update installation and removal guidance to explain copy refresh and safe
  handling of existing installations.
- Clarify the existing unauthorized Publisher preflight handoff fields so the
  native smoke uses the validator-compatible `NEXT_STATE=BLOCKED` output.
- Add focused tests and a fresh native smoke gate covering the regular-file
  installation, all five sequential Agent names, no-write handoffs, stale
  `ATTEMPT_ID` rejection, and unauthorized Publisher preflight blocking.
- Keep the existing five TOML definitions, role names, state-machine routing,
  and project `.agents/shared` link unchanged; this only makes an existing
  Publisher handoff requirement explicit.

## Capabilities

### New Capabilities

- `codex-agent-installation`: Install and diagnose native Codex Agent profiles
  in a form that Codex can discover reliably.

### Modified Capabilities

<!-- No existing main specs are present; this change introduces the capability. -->

## Impact

- Affects the installation and removal instructions in `README.md`, the
  global checks in `scripts/doctor.sh`, and their focused tests.
- Installed TOMLs will no longer track source edits through filesystem links;
  users must rerun the installation step to refresh them.
- Does not change business code, the five Agent names or runtime state-machine
  routing, the current consolidation Change, or Codex itself. It clarifies the
  existing Publisher handoff contract and role instructions.
- It is sequenced after the consolidation Change has a stable reviewed
  revision; shared paths may be updated only for this Change’s copy/discovery
  and blocked-handoff behavior, while consolidation-only edits remain out of
  scope.
- No new runtime dependency is required.
