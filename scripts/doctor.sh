#!/usr/bin/env bash

set -euo pipefail

if ! { [[ $# -eq 1 && "${1-}" == "--global" ]] ||
       [[ $# -eq 2 && "${1-}" == "--project" ]]; }; then
  echo "FAIL usage: doctor.sh --global | --project PATH"
  exit 2
fi

if ! command -v python3 >/dev/null 2>&1 ||
   ! python3 -c 'import sys; assert sys.version_info >= (3, 11); import tomllib' >/dev/null 2>&1; then
  echo "FAIL python3: Python 3.11+ with stdlib tomllib is required"
  exit 1
fi

python3 - "$0" "$@" <<'PY'
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib


REPOSITORY = Path(sys.argv[1]).resolve().parent.parent
FAILED = False
SENSITIVE_VALUES = sorted({
    value for name, value in os.environ.items()
    if value and any(marker in name.upper() for marker in ("TOKEN", "KEY", "SECRET"))
}, key=len, reverse=True)


def redact(message):
    for value in SENSITIVE_VALUES:
        message = message.replace(value, "[redacted]")
    return message


def display_path(path):
    return json.dumps(redact(str(path)))


def report(status, message):
    global FAILED
    FAILED = FAILED or status == "FAIL"
    print(status + " " + redact(message))


def check(valid, message):
    report("PASS" if valid else "FAIL", message)
    return valid


def run(arguments, cwd=None):
    try:
        return subprocess.run(
            arguments, cwd=cwd, capture_output=True, text=True, errors="replace",
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
    except OSError:
        return subprocess.CompletedProcess(arguments, 127, "", "")


def correct_link(link, source):
    return source.exists() and link.is_symlink() and link.resolve() == source.resolve()


def global_checks():
    home = Path.home()
    skill = REPOSITORY / "skills/openspec-dev-team"
    check((skill / "SKILL.md").is_file() and correct_link(
        home / ".codex/skills/openspec-dev-team", skill), "skill source and installed link")
    agents = {
        "openspec-explore-proposal": ("gpt-5.6-sol", "medium", "workspace-write"),
        "openspec-proposal-reviewer": ("gpt-5.6-terra", "high", "read-only"),
        "openspec-apply-executor": ("gpt-5.6-terra", "high", "workspace-write"),
        "openspec-pre-archive-auditor": ("gpt-5.6-terra", "high", "workspace-write"),
        "openspec-archivist-publisher": ("gpt-5.6-luna", "medium", "workspace-write"),
    }
    for name, expected in agents.items():
        source = REPOSITORY / "profiles/codex/agents" / (name + ".toml")
        if not check(correct_link(home / ".codex/agents" / source.name, source),
                     "agent " + name + " source and installed link"):
            continue
        try:
            profile = tomllib.loads(source.read_text())
            valid = all(isinstance(profile.get(key), str) and profile[key].strip() for key in (
                "name", "description", "model", "model_reasoning_effort",
                "sandbox_mode", "developer_instructions",
            ))
            valid = valid and profile["name"] == name and tuple(profile[key] for key in (
                "model", "model_reasoning_effort", "sandbox_mode",
            )) == expected
        except (OSError, ValueError):
            valid = False
        check(valid, "agent " + name + " required TOML fields and exact model/reasoning")
    for name in ("doctor.sh", "link-project.sh", "workflow-state.py"):
        path = REPOSITORY / "scripts" / name
        check(path.is_file() and os.access(path, os.X_OK), "executable scripts/" + name)
    for platform in ("pi", "claude-code"):
        path = REPOSITORY / "profiles" / platform / "README.md"
        try:
            valid = "template-only" in path.read_text()
        except OSError:
            valid = False
        check(valid, platform + " template-only label")


def scalar(value):
    value = value.strip()
    if value.startswith(('"', "'", "[")):
        return ast.literal_eval(value)
    value = value.split(" #", 1)[0].strip()
    if value.lower() in {"null", "~", "true", "false"}:
        return None
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value


def project_config(path, git_root, openspec_root):
    # Read the scalar/list YAML subset used by templates/project.md, without executing it.
    fields = {}
    for block in re.findall(r"^```ya?ml\s*\n(.*?)^```\s*$", path.read_text(), re.M | re.S):
        current = None
        for line in block.splitlines():
            match = re.match(r"^([a-z_]+):\s*(.*)$", line)
            if match:
                current, value = match.groups()
                if current in fields:
                    raise ValueError("duplicate project field")
                fields[current] = scalar(value) if value else []
            elif re.match(r"^\s+-\s+", line) and current:
                fields[current].append(scalar(line.strip()[2:]))
    scalars = ("project_name", "project_realpath", "main_branch", "expected_remote", "openspec_root")
    lists = ("stack", "quality_gates", "protected_data", "project_constraints", "project_skills")
    if not all(isinstance(fields.get(key), str) and fields[key].strip() for key in scalars):
        return False
    if not all(isinstance(fields.get(key), list) and all(
        isinstance(value, str) and value.strip() for value in fields[key]
    ) for key in lists):
        return False
    return (bool(fields["stack"]) and bool(fields["quality_gates"])
            and Path(fields["project_realpath"]).is_absolute()
            and Path(fields["project_realpath"]).resolve() == git_root
            and (git_root / fields["openspec_root"]).resolve() == openspec_root)


def untracked_paths(git_root):
    result = run(["git", "ls-files", "--others", "--exclude-standard", "-z"], git_root)
    if not check(result.returncode == 0, "untracked paths inspection"):
        return
    paths = set(filter(None, result.stdout.split("\0")))
    baselines = []
    for path in sorted((git_root / ".agents/state").glob("*.json")):
        try:
            state = json.loads(path.read_text())
            baseline = state["UNTRACKED_BASELINE"]
            if not isinstance(baseline, list) or not all(isinstance(item, str) for item in baseline):
                raise ValueError("invalid baseline")
            if state.get("STATE") not in {"DONE", "CANCELLED"}:
                baselines.append(set(baseline))
        except (OSError, ValueError, KeyError, TypeError):
            report("WARN", "untracked baseline state could not be verified")
    baseline = set.intersection(*baselines) if baselines else paths
    for path in sorted(paths):
        if path in baseline:
            report("PASS", "untracked baseline " + display_path(path))
        else:
            report("WARN", "untracked new " + display_path(path))


def lock_checks(agents):
    for path in sorted(agents.glob("*.lock")):
        label = display_path(path.name)
        try:
            lock = json.loads(path.read_text())
            pid = lock.get("PID", lock.get("pid"))
            session = lock.get("SESSION_ID", lock.get("session_id"))
            if isinstance(pid, bool) or not re.fullmatch(r"[1-9][0-9]*", str(pid)):
                raise ValueError("unverifiable process")
            pid = int(pid)
            os.kill(pid, 0)
            if session is not None:
                if isinstance(session, bool) or not re.fullmatch(r"[1-9][0-9]*", str(session)):
                    raise ValueError("unverifiable session")
                if os.getsid(pid) != int(session):
                    report("WARN", "stale lock " + label)
                    continue
            report("PASS", "lock owner present " + label)
        except ProcessLookupError:
            report("WARN", "stale lock " + label)
        except (OSError, ValueError, AttributeError, OverflowError):
            report("WARN", "lock identity could not be verified " + label)


def project_checks(argument):
    project = Path(argument).resolve()
    if not check(project.is_dir(), "project directory"):
        return
    result = run(["git", "rev-parse", "--show-toplevel"], project)
    if not check(result.returncode == 0 and bool(result.stdout.strip()), "Git root"):
        return
    git_root = Path(result.stdout.strip()).resolve()
    if not check(project.is_relative_to(git_root), "project inside Git root"):
        return
    location = project
    while not (location / "openspec").is_dir() and location != git_root:
        location = location.parent
    openspec_root = location / "openspec"
    if check(openspec_root.is_dir(), "OpenSpec root"):
        result = run(["openspec", "list", "--json"], location)
        try:
            valid = result.returncode == 0 and isinstance(json.loads(result.stdout), (dict, list))
        except ValueError:
            valid = False
        check(valid, "OpenSpec list --json")
        check(run(["openspec", "doctor"], location).returncode == 0, "OpenSpec doctor")
    agents = git_root / ".agents"
    for name in ("shared", "team"):
        check(correct_link(agents / name, REPOSITORY / "agents" / name), ".agents/" + name + " link")
    try:
        valid = not (agents / "project.md").is_symlink() and project_config(
            agents / "project.md", git_root, openspec_root.resolve(),
        )
    except (OSError, ValueError, SyntaxError, AttributeError):
        valid = False
    check(valid, "project config fields and root bindings")
    for path in (".agents/state/.doctor-probe", ".agents/runs/.doctor-probe", ".agents/.doctor-probe.lock"):
        check(run(["git", "check-ignore", "--quiet", "--", path], git_root).returncode == 0,
              "runtime ignore " + path)
    for arguments, label in (([], "tracked worktree"), (["--cached"], "index")):
        result = run(["git", "diff", "--quiet", "--no-ext-diff", *arguments], git_root)
        if result.returncode == 1:
            report("FAIL", "NEEDS_HUMAN: " + label + " has changes")
        else:
            check(result.returncode == 0, label + " inspection")
    untracked_paths(git_root)
    lock_checks(agents)


try:
    report("PASS", "python3: Python 3.11+ with stdlib tomllib available")
    dependencies = [check(run([command, "--version"]).returncode == 0, command + " available")
                    for command in ("git", "openspec")]
    if sys.argv[2] == "--global":
        global_checks()
    elif all(dependencies):
        project_checks(sys.argv[3])
except (OSError, ValueError, RuntimeError):
    report("FAIL", "diagnostic input could not be inspected")
sys.exit(1 if FAILED else 0)
PY
