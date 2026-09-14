# OpenSpec Development Team for Codex

This repository installs a serial, five-role OpenSpec development team in
Codex. The team explores a request, creates and reviews its Change, applies and
audits it, then optionally archives and publishes it after an explicit Human
Gate. OpenSpec remains the lifecycle source of truth.

## Prerequisites

- Codex with native custom-agent discovery
- OpenSpec CLI
- Git, with the target project working directly on `main`
- `python3` resolved from `PATH` must be Python 3.11+ (`tomllib` is required);
  repository validation currently uses Python 3.13

The `profiles/pi` and `profiles/claude-code` mappings are template-only; this
installation uses the Codex profiles.

## Installation

From this repository root, preflight every destination before creating the
skill link or copying a profile. The skill remains a symlink, but the five
native Agent profiles must be regular files so Codex can discover them.
Both `-e` and `-L` are required because `-e` alone misses a broken symlink.

```bash
set -eu
repository=$(pwd -P)

require_absent() {
  path=$1
  if [ -e "$path" ] || [ -L "$path" ]; then
    printf 'Refusing existing installation path: %s\n' "$path" >&2
    return 1
  fi
}

install_link() {
  source=$1
  link=$2
  require_absent "$link"
  ln -s -- "$source" "$link"
}

install_copy() {
  source=$1
  destination=$2
  require_absent "$destination"
  cp -- "$source" "$destination"
}

for path in \
  "$HOME/.codex/skills/openspec-dev-team" \
  "$HOME/.codex/agents/openspec-explore-proposal.toml" \
  "$HOME/.codex/agents/openspec-proposal-reviewer.toml" \
  "$HOME/.codex/agents/openspec-apply-executor.toml" \
  "$HOME/.codex/agents/openspec-pre-archive-auditor.toml" \
  "$HOME/.codex/agents/openspec-archivist-publisher.toml"
do
  require_absent "$path"
done

mkdir -p "$HOME/.codex/skills" "$HOME/.codex/agents"
install_link "$repository/skills/openspec-dev-team" "$HOME/.codex/skills/openspec-dev-team"
install_copy "$repository/profiles/codex/agents/openspec-explore-proposal.toml" "$HOME/.codex/agents/openspec-explore-proposal.toml"
install_copy "$repository/profiles/codex/agents/openspec-proposal-reviewer.toml" "$HOME/.codex/agents/openspec-proposal-reviewer.toml"
install_copy "$repository/profiles/codex/agents/openspec-apply-executor.toml" "$HOME/.codex/agents/openspec-apply-executor.toml"
install_copy "$repository/profiles/codex/agents/openspec-pre-archive-auditor.toml" "$HOME/.codex/agents/openspec-pre-archive-auditor.toml"
install_copy "$repository/profiles/codex/agents/openspec-archivist-publisher.toml" "$HOME/.codex/agents/openspec-archivist-publisher.toml"
"$repository/scripts/doctor.sh" --global
```

Custom-agent discovery may require a new Codex session after installation. The
profile copies do not track source edits automatically; rerun this installation
to refresh them. Existing files, directories, and symlinks are refused rather
than overwritten, so an older installation must be migrated explicitly. The
global diagnostic reports source drift and names the profile that must be
reinstalled.

## Configuration model

Each default specialist has exactly one native TOML definition under
`profiles/codex/agents/`; role-specific Markdown files are not used. The five
installed profiles retain their documented names, models, reasoning efforts,
sandbox modes, and Codex discovery filenames. Shared workflow and handoff
contracts remain separate because they are cross-Agent guarantees, not role
definitions.

## Project bootstrap

Preview, then configure one target Git root:

```bash
scripts/link-project.sh --dry-run /absolute/path/to/project
scripts/link-project.sh /absolute/path/to/project
```

The script links only `.agents/shared`; `.agents/team` is obsolete and is not
created or required. It creates local ignored runtime directories and copies
`templates/project.md` to `.agents/project.md`. Edit that project-owned file and verify at least
`project_realpath`, `main_branch`, `expected_remote`, `openspec_root`, and
`quality_gates`. Then run:

```bash
scripts/doctor.sh --project /absolute/path/to/project
```

## Use

Start from the configured project in a clean Codex session:

```text
$openspec-dev-team <request> [--publish]
```

`--publish` records intent; it does not bypass authorization. The workflow
stops at the Human Gate in `AWAITING_EXPLORE_APPROVAL`, where the saved Explore
Result may be approved, revised, or rejected. Publication requires explicit
authorization bound there or explicitly granted later at `READY_TO_PUBLISH`,
where a passing audit stops without authorization. The Orchestrator records a
later decision with `workflow-state.py authorize-publish --state <state>
--evidence <human-decision-file>` before the `AUTHORIZE_PUBLISH` transition.

To continue an existing run, invoke the skill with its `run-id`. It resumes the
state under `.agents/state/` and reads the saved `REQUEST_ARTIFACT`; it does not
create a duplicate request. A `BLOCKED` run needs fresh resolution evidence.
Before restarting an interrupted normal stage, the Orchestrator uses
`workflow-state.py dispatch --state <state>` to issue a new `ATTEMPT_ID` and
reject late handoffs from the interrupted attempt.
`PUBLISHING` resumes from reconciled receipt state, never from the beginning.

Run read-only role wiring diagnostics with fixture artifacts:

```text
$openspec-dev-team smoke
```

For native compatibility evidence, use a disposable fixture and an isolated
temporary `CODEX_HOME` containing the skill symlink and regular profile copies.
The setup shape is:

```bash
TEAM_ROOT=/absolute/path/to/openspec-dev-team
CODEX_HOME=/tmp/openspec-codex-home
FIXTURE=/tmp/openspec-codex-fixture  # prepared disposable Git project
mkdir -p "$CODEX_HOME/skills" "$CODEX_HOME/agents"
ln -s "$TEAM_ROOT/skills/openspec-dev-team" "$CODEX_HOME/skills/openspec-dev-team"
for name in openspec-explore-proposal openspec-proposal-reviewer openspec-apply-executor openspec-pre-archive-auditor openspec-archivist-publisher; do
  cp "$TEAM_ROOT/profiles/codex/agents/$name.toml" "$CODEX_HOME/agents/$name.toml"
done
CODEX_HOME="$CODEX_HOME" codex exec --ephemeral --sandbox read-only \
  --ignore-user-config -C "$FIXTURE" '$openspec-dev-team smoke'
```

Record `codex --version`, snapshot fixture/project paths before and after, and
fail on any attempted write or changed path. The full handoff, stale-attempt,
and unauthorized-Publisher checks are defined in the skill's Smoke section.

For installation or project diagnostics, use `doctor.sh --global` or
`doctor.sh --project /absolute/path/to/project` respectively. Diagnostics validate
all five TOML profiles and the shared-only project wiring.

## Codex model map

| Agent | Model | Reasoning | Sandbox |
| --- | --- | --- | --- |
| `openspec-explore-proposal` | `gpt-5.6-sol` | `medium` | `workspace-write` |
| `openspec-proposal-reviewer` | `gpt-5.6-terra` | `high` | `read-only` |
| `openspec-apply-executor` | `gpt-5.6-terra` | `high` | `workspace-write` |
| `openspec-pre-archive-auditor` | `gpt-5.6-terra` | `high` | `workspace-write` |
| `openspec-archivist-publisher` | `gpt-5.6-luna` | `medium` | `workspace-write` |

## Removal

Remove only installation paths that this checkout still owns. Set both absolute
paths. The skill and project wiring are removed only when `-L` and `readlink`
confirm their exact targets. Older repository-owned profile symlinks can be
removed by the same target check; regular profile copies are removed only when
`cmp` confirms that they still match this checkout.

```bash
repository=/absolute/path/to/openspec-dev-team
project=/absolute/path/to/project

unlink_if_target() {
  link=$1
  target=$2
  if [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ]; then
    unlink "$link"
  fi
}

unlink_if_target "$HOME/.codex/skills/openspec-dev-team" "$repository/skills/openspec-dev-team"

remove_copy_if_match() {
  source=$1
  copy=$2
  if [ -f "$copy" ] && [ ! -L "$copy" ] && cmp -s "$source" "$copy"; then
    unlink "$copy"
  elif [ -e "$copy" ] || [ -L "$copy" ]; then
    printf 'Preserving unowned or drifted profile: %s\n' "$copy" >&2
  fi
}

for name in openspec-explore-proposal openspec-proposal-reviewer openspec-apply-executor openspec-pre-archive-auditor openspec-archivist-publisher; do
  unlink_if_target "$HOME/.codex/agents/$name.toml" "$repository/profiles/codex/agents/$name.toml"
  remove_copy_if_match "$repository/profiles/codex/agents/$name.toml" "$HOME/.codex/agents/$name.toml"
done
unlink_if_target "$project/.agents/shared" "$repository/agents/shared"
unlink_if_target "$project/.agents/team" "$repository/agents/team"
```

Because no manifest is used, profile removal uses `cmp` for content-based ownership
rather than proof of provenance. Do not run removal automatically
when an identical user-created file may be present; handle that path manually.

Older bootstraps may leave an obsolete `.agents/team` symlink. Remove it only
when `-L` and `readlink` confirm that it targets this checkout; never delete a
regular directory or an unrelated link. A drifted or unowned profile copy is
also preserved for manual review. This intentionally leaves project-owned
`.agents/project.md` and local run evidence in place.
