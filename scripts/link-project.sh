#!/usr/bin/env bash

set -euo pipefail

usage() {
  echo "Usage: $0 [--dry-run] PROJECT_PATH" >&2
}

fail() {
  echo "link-project.sh: $1" >&2
  exit 1
}

dry_run=false
if [[ "${1-}" == "--dry-run" ]]; then
  dry_run=true
  shift
fi

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
repository_dir=$(CDPATH= cd -- "$script_dir/.." && pwd -P)
shared_source="$repository_dir/agents/shared"
team_source="$repository_dir/agents/team"
project_template="$repository_dir/templates/project.md"

[[ -d "$shared_source" ]] || fail "missing source directory: $shared_source"
[[ -d "$team_source" ]] || fail "missing source directory: $team_source"
[[ -f "$project_template" ]] || fail "missing project template: $project_template"
[[ -d "$1" ]] || fail "project path is not a directory: $1"

project_dir=$(CDPATH= cd -- "$1" && pwd -P)
if ! git_root=$(git -C "$project_dir" rev-parse --show-toplevel 2>/dev/null); then
  fail "project path is not a Git repository: $project_dir"
fi
git_root=$(CDPATH= cd -- "$git_root" && pwd -P)
[[ "$project_dir" == "$git_root" ]] || fail "project path is not the Git repository root: $project_dir"

agents_dir="$project_dir/.agents"
shared_link="$agents_dir/shared"
team_link="$agents_dir/team"
project_file="$agents_dir/project.md"
state_dir="$agents_dir/state"
runs_dir="$agents_dir/runs"
gitignore_file="$agents_dir/.gitignore"

if [[ -L "$agents_dir" ]] || [[ -e "$agents_dir" && ! -d "$agents_dir" ]]; then
  fail "conflicting path: $agents_dir"
fi

check_link() {
  local link_path=$1
  local source_path=$2

  if [[ -L "$link_path" ]]; then
    [[ "$link_path" -ef "$source_path" ]] || fail "wrong symlink target: $link_path"
  elif [[ -e "$link_path" ]]; then
    fail "conflicting path: $link_path"
  fi
}

check_directory() {
  local directory_path=$1

  if [[ -L "$directory_path" ]] || [[ -e "$directory_path" && ! -d "$directory_path" ]]; then
    fail "conflicting path: $directory_path"
  fi
}

check_link "$shared_link" "$shared_source"
check_link "$team_link" "$team_source"

if [[ -L "$project_file" ]] || [[ -e "$project_file" && ! -f "$project_file" ]]; then
  fail "conflicting path: $project_file"
fi

check_directory "$state_dir"
check_directory "$runs_dir"

if [[ -L "$gitignore_file" ]] || [[ -e "$gitignore_file" && ! -f "$gitignore_file" ]]; then
  fail "conflicting path: $gitignore_file"
fi
if [[ -f "$gitignore_file" ]] && ! printf '/state/\n/runs/\n/*.lock\n' | cmp -s - "$gitignore_file"; then
  fail "conflicting file contents: $gitignore_file"
fi

if [[ "$dry_run" == true ]]; then
  echo "Would configure $agents_dir"
  echo "Would link $shared_link -> $shared_source"
  echo "Would link $team_link -> $team_source"
  exit 0
fi

mkdir -p "$agents_dir"
[[ -L "$shared_link" ]] || ln -s "$shared_source" "$shared_link"
[[ -L "$team_link" ]] || ln -s "$team_source" "$team_link"
[[ -f "$project_file" ]] || cp "$project_template" "$project_file"
mkdir -p "$state_dir" "$runs_dir"
if [[ ! -f "$gitignore_file" ]]; then
  printf '/state/\n/runs/\n/*.lock\n' > "$gitignore_file"
fi

echo "Configured $agents_dir"
