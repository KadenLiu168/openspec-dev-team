# OpenSpec Development Team for Codex

This repository installs a serial, five-role OpenSpec development team in
Codex. The team explores a request, creates and reviews its Change, applies and
audits it, then optionally archives and publishes it after an explicit Human
Gate. OpenSpec remains the lifecycle source of truth.

## Prerequisites

- Codex with native custom-agent discovery
- OpenSpec CLI
- Git, with the target project working directly on `main`
- Python 3.11+ (`tomllib` is required); repository validation currently uses
  Python 3.13

The `profiles/pi` and `profiles/claude-code` mappings are template-only; this
installation uses the Codex profiles.

## Installation

From this repository root, create only absent links (plain `ln -s` refuses to
replace an existing path):

```bash
mkdir -p "$HOME/.codex/skills" "$HOME/.codex/agents"
ln -s "$PWD/skills/openspec-dev-team" "$HOME/.codex/skills/openspec-dev-team"
ln -s "$PWD/profiles/codex/agents/openspec-explore-proposal.toml" "$HOME/.codex/agents/openspec-explore-proposal.toml"
ln -s "$PWD/profiles/codex/agents/openspec-proposal-reviewer.toml" "$HOME/.codex/agents/openspec-proposal-reviewer.toml"
ln -s "$PWD/profiles/codex/agents/openspec-apply-executor.toml" "$HOME/.codex/agents/openspec-apply-executor.toml"
ln -s "$PWD/profiles/codex/agents/openspec-pre-archive-auditor.toml" "$HOME/.codex/agents/openspec-pre-archive-auditor.toml"
ln -s "$PWD/profiles/codex/agents/openspec-archivist-publisher.toml" "$HOME/.codex/agents/openspec-archivist-publisher.toml"
scripts/doctor.sh --global
```

Custom-agent discovery may require a new Codex session after installation.

## Project bootstrap

Preview, then configure one target Git root:

```bash
scripts/link-project.sh --dry-run /absolute/path/to/project
scripts/link-project.sh /absolute/path/to/project
```

The script links `.agents/shared` and `.agents/team`, creates local ignored
runtime directories, and copies `templates/project.md` to
`.agents/project.md`. Edit that project-owned file and verify at least
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
authorization bound there; otherwise a passing audit stops at
`READY_TO_PUBLISH`.

To continue an existing run, invoke the skill with its `run-id`. It resumes the
state under `.agents/state/` and reads the saved `REQUEST_ARTIFACT`; it does not
create a duplicate request. A `BLOCKED` run needs fresh resolution evidence.
`PUBLISHING` resumes from reconciled receipt state, never from the beginning.

Run read-only role wiring diagnostics with fixture artifacts:

```text
$openspec-dev-team smoke
```

For installation or project diagnostics, use `doctor.sh --global` or
`doctor.sh --project /absolute/path/to/project` respectively.

## Codex model map

| Agent | Model | Reasoning | Sandbox |
| --- | --- | --- | --- |
| `openspec-explore-proposal` | `gpt-5.6-sol` | `medium` | `workspace-write` |
| `openspec-proposal-reviewer` | `gpt-5.6-terra` | `high` | `read-only` |
| `openspec-apply-executor` | `gpt-5.6-terra` | `high` | `workspace-write` |
| `openspec-pre-archive-auditor` | `gpt-5.6-terra` | `high` | `workspace-write` |
| `openspec-archivist-publisher` | `gpt-5.6-luna` | `medium` | `workspace-write` |

## Removal

Remove only links that still target this checkout. Set both absolute paths,
then verify each path with `-L` and `readlink` before `unlink`:

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
for name in openspec-explore-proposal openspec-proposal-reviewer openspec-apply-executor openspec-pre-archive-auditor openspec-archivist-publisher; do
  unlink_if_target "$HOME/.codex/agents/$name.toml" "$repository/profiles/codex/agents/$name.toml"
done
unlink_if_target "$project/.agents/shared" "$repository/agents/shared"
unlink_if_target "$project/.agents/team" "$repository/agents/team"
```

This intentionally leaves project-owned `.agents/project.md` and local run
evidence in place.
