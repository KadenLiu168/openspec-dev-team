"""Exercise doctor against isolated installations and Git projects."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
SCRIPT = REPOSITORY / "scripts/doctor.sh"
REAL_GIT = shutil.which("git")
AGENTS = (
    "openspec-explore-proposal", "openspec-proposal-reviewer",
    "openspec-apply-executor", "openspec-pre-archive-auditor",
    "openspec-archivist-publisher",
)


class DoctorTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.repository = self.root / "installation"
        for name in ("agents", "profiles", "skills", "templates", "scripts"):
            shutil.copytree(REPOSITORY / name, self.repository / name)
        (self.repository / "skills/openspec-dev-team/SKILL.md").write_text(
            "---\nname: openspec-dev-team\ndescription: Fixture skill.\n---\n"
        )
        for path in (self.repository / "scripts").iterdir():
            path.chmod(0o755)
        self.home = self.root / "home"
        skill_link = self.home / ".codex/skills/openspec-dev-team"
        skill_link.parent.mkdir(parents=True)
        skill_link.symlink_to(self.repository / "skills/openspec-dev-team")
        agent_dir = self.home / ".codex/agents"
        agent_dir.mkdir()
        for name in AGENTS:
            self.copy_profile(name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "calls.jsonl"
        self.project = self.root / "project"
        self.project.mkdir()
        self.env = {
            "HOME": str(self.home), "PATH": str(self.bin) + ":/usr/bin:/bin",
            "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C",
            "DOCTOR_TEST_LOG": str(self.log),
            "DOCTOR_TEST_OPENROOT": str(self.project),
            "DOCTOR_TEST_TOKEN": "token-value-do-not-print",
            "DOCTOR_TEST_KEY": "key-value-do-not-print",
            "DOCTOR_TEST_SECRET": "secret-value-do-not-print",
        }
        self.write_executable("python3", """
version = os.environ.get("DOCTOR_TEST_PYTHON_VERSION")
if version and sys.argv[1:2] == ["-c"]:
    probe = "import sys; sys.version_info = tuple(" + version + "); " + sys.argv[2]
    os.execv(sys.executable, [sys.executable, "-c", probe])
os.execv(sys.executable, [sys.executable, *sys.argv[1:]])
""")
        self.write_executable("git", """
arguments = sys.argv[1:]
command = arguments[2] if arguments[:1] == ["-C"] else arguments[0]
allowed = {"--version", "rev-parse", "check-ignore", "diff", "status", "ls-files"}
if command not in allowed:
    sys.exit(91)
if os.environ.get("DOCTOR_TEST_GIT_FAIL") == command:
    print(os.environ["DOCTOR_TEST_SECRET"], file=sys.stderr)
    sys.exit(128)
os.execv(REAL_GIT, [REAL_GIT, *arguments])
""", prefix="REAL_GIT = " + repr(REAL_GIT) + "\n")
        self.write_executable("openspec", """
arguments = sys.argv[1:]
if arguments == ["--version"]:
    print("1.0.0")
    sys.exit(0)
if os.getcwd() != os.environ["DOCTOR_TEST_OPENROOT"]:
    sys.exit(92)
if arguments not in (["list", "--json"], ["doctor"]):
    sys.exit(93)
failure = os.environ.get("DOCTOR_TEST_OPENSPEC_FAIL")
if failure == arguments[0]:
    print(os.environ["DOCTOR_TEST_TOKEN"])
    print(os.environ["DOCTOR_TEST_KEY"], file=sys.stderr)
    sys.exit(1)
if arguments[0] == "list":
    print("not-json" if failure == "json" else '{"changes": []}')
else:
    print(os.environ["DOCTOR_TEST_SECRET"])
""")
        self.git("init", "--quiet", "--initial-branch=main")
        self.agents = self.project / ".agents"
        self.agents.mkdir()
        (self.agents / "shared").symlink_to(self.repository / "agents/shared")
        (self.agents / "state").mkdir()
        (self.agents / "runs").mkdir()
        (self.agents / ".gitignore").write_text("/state/\n/runs/\n/*.lock\n")
        (self.project / "openspec").mkdir()
        (self.project / "openspec/config.yaml").write_text("schema: spec-driven\n")
        (self.project / "tracked.txt").write_text("original\n")
        self.config = (REPOSITORY / "templates/project.md").read_text().replace(
            "example-project", "fixture-project"
        ).replace("/absolute/path/to/fixture-project", str(self.project))
        self.write_config(self.config)
        self.git("add", ".agents/.gitignore", ".agents/project.md", ".agents/shared",
                 "openspec/config.yaml", "tracked.txt")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "--quiet", "-m", "fixture")

    def write_executable(self, name, body, prefix=""):
        executable = self.bin / name
        executable.write_text(
            "#!" + sys.executable + "\nimport json, os, sys\n" + prefix
            + "with open(os.environ['DOCTOR_TEST_LOG'], 'a') as log:\n"
            + "    log.write(json.dumps([os.path.basename(sys.argv[0]), os.getcwd(), sys.argv[1:]]) + '\\n')\n"
            + body
        )
        executable.chmod(0o755)

    def git(self, *arguments):
        return subprocess.run([REAL_GIT, "-C", str(self.project), *arguments],
                              check=True, capture_output=True, text=True, env=self.env)

    def write_config(self, content):
        (self.agents / "project.md").write_text(content)

    def copy_profile(self, name):
        (self.home / ".codex/agents" / (name + ".toml")).write_bytes(
            (self.repository / "profiles/codex/agents" / (name + ".toml")).read_bytes()
        )

    def run_doctor(self, *arguments, success=True):
        self.assertTrue(SCRIPT.is_file(), "missing scripts/doctor.sh")
        result = subprocess.run(
            ["/bin/bash", str(self.repository / "scripts/doctor.sh"), *map(str, arguments)],
            cwd=self.root, env=self.env, capture_output=True, text=True,
        )
        output = result.stdout + result.stderr
        for name, value in self.env.items():
            if any(marker in name for marker in ("TOKEN", "KEY", "SECRET")):
                self.assertNotIn(name, output)
                self.assertNotIn(value, output)
                self.assertNotIn(json.dumps(value)[1:-1], output)
        self.assertNotEqual(output, "")
        for line in output.splitlines():
            self.assertRegex(line, r"^(PASS|WARN|FAIL) ")
        if success:
            self.assertEqual(result.returncode, 0, output)
            self.assertNotIn("FAIL ", output)
        else:
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn("FAIL ", output)
        return output

    def test_global_valid_installation(self):
        output = self.run_doctor("--global")
        for name in AGENTS:
            self.assertIn("PASS agent " + name, output)
        self.assertIn("PASS skill", output)
        self.assertIn("PASS python3", output)

    def test_global_rejects_matching_agent_symlinks(self):
        for name in AGENTS:
            link = self.home / ".codex/agents" / (name + ".toml")
            link.unlink()
            link.symlink_to(self.repository / "profiles/codex/agents" / (name + ".toml"))
            with self.subTest(agent=name):
                output = self.run_doctor("--global", success=False)
                self.assertIn("regular file", output)
            link.unlink()
            self.copy_profile(name)

    def test_global_missing_skill_link(self):
        (self.home / ".codex/skills/openspec-dev-team").unlink()
        self.assertIn("FAIL skill", self.run_doctor("--global", success=False))

    def test_global_wrong_or_regular_skill_link(self):
        link = self.home / ".codex/skills/openspec-dev-team"
        link.unlink()
        link.symlink_to(self.repository / "agents")
        self.run_doctor("--global", success=False)
        link.unlink()
        link.mkdir()
        self.run_doctor("--global", success=False)

    def test_global_missing_agent_link(self):
        for name in AGENTS:
            link = self.home / ".codex/agents" / (name + ".toml")
            link.unlink()
            with self.subTest(agent=name):
                self.assertIn("FAIL agent " + name, self.run_doctor("--global", success=False))
            self.copy_profile(name)

    def test_global_wrong_agent_target(self):
        link = self.home / ".codex/agents" / (AGENTS[0] + ".toml")
        link.unlink()
        link.symlink_to(self.repository / "profiles/codex/agents" / (AGENTS[1] + ".toml"))
        self.run_doctor("--global", success=False)
        link.unlink()
        self.copy_profile(AGENTS[0])

    def test_global_rejects_installed_model_and_reasoning_drift_for_every_agent(self):
        for name in AGENTS:
            path = self.home / ".codex/agents" / (name + ".toml")
            original = path.read_text()
            for key in ("model", "model_reasoning_effort"):
                with self.subTest(agent=name, key=key):
                    path.write_text("\n".join(
                        key + ' = "incorrect"' if line.startswith(key + " =") else line
                        for line in original.splitlines()
                    ))
                    self.run_doctor("--global", success=False)
            path.write_text(original)

    def test_global_rejects_missing_required_toml_keys_and_malformed_toml(self):
        path = self.home / ".codex/agents" / (AGENTS[0] + ".toml")
        original = path.read_text()
        for key in ("name", "description", "model", "model_reasoning_effort", "sandbox_mode"):
            with self.subTest(key=key):
                path.write_text("\n".join(line for line in original.splitlines()
                                          if not line.startswith(key + " =")))
                self.run_doctor("--global", success=False)
        for content in (original.split("developer_instructions")[0], "invalid = ["):
            path.write_text(content)
            self.run_doctor("--global", success=False)
        path.write_text(original)

    def test_global_rejects_source_drift_in_installed_profile(self):
        path = self.home / ".codex/agents" / (AGENTS[0] + ".toml")
        original = path.read_bytes()
        path.write_bytes(original + b"\n# edited after installation\n")
        output = self.run_doctor("--global", success=False)
        self.assertIn("source drift", output)
        path.write_bytes(original)

    def test_global_requires_concrete_skill_source(self):
        (self.repository / "skills/openspec-dev-team/SKILL.md").unlink()
        self.run_doctor("--global", success=False)

    def test_global_requires_executable_scripts(self):
        for name in ("doctor.sh", "link-project.sh", "workflow-state.py"):
            path = self.repository / "scripts" / name
            if not path.exists():
                continue
            mode = path.stat().st_mode
            path.chmod(0o644)
            with self.subTest(script=name):
                self.assertIn("FAIL executable", self.run_doctor("--global", success=False))
            path.chmod(mode)

    def test_global_requires_template_only_platform_labels(self):
        for name in ("pi", "claude-code"):
            path = self.repository / "profiles" / name / "README.md"
            original = path.read_text()
            path.write_text(original.replace("template-only", "validated"))
            with self.subTest(platform=name):
                self.run_doctor("--global", success=False)
            path.write_text(original)

    def test_python_older_than_311_is_an_actionable_failure(self):
        self.env["DOCTOR_TEST_PYTHON_VERSION"] = "[3, 10, 16]"
        output = self.run_doctor("--global", success=False)
        self.assertIn("python3", output)
        self.assertIn("3.11", output)

    def test_python_311_satisfies_the_exact_capability_boundary(self):
        self.env["DOCTOR_TEST_PYTHON_VERSION"] = "[3, 11, 0]"
        self.run_doctor("--global")

    def test_missing_dependencies_are_failures(self):
        self.env["PATH"] = str(self.bin)
        for name in ("git", "openspec", "python3"):
            executable = self.bin / name
            backup = self.bin / (name + ".unavailable")
            executable.rename(backup)
            with self.subTest(dependency=name):
                self.assertIn("FAIL " + name, self.run_doctor("--global", success=False))
            backup.rename(executable)

    def test_dependency_failure_does_not_echo_command_output(self):
        self.env["DOCTOR_TEST_GIT_FAIL"] = "--version"
        self.assertIn("FAIL git", self.run_doctor("--global", success=False))

    def test_project_valid_from_nested_directory_and_read_only(self):
        nested = self.project / "src/nested"
        nested.mkdir(parents=True)
        before = {str(path.relative_to(self.project)): path.read_bytes()
                  for path in self.project.rglob("*") if path.is_file() and not path.is_symlink()}
        output = self.run_doctor("--project", nested)
        after = {str(path.relative_to(self.project)): path.read_bytes()
                 for path in self.project.rglob("*") if path.is_file() and not path.is_symlink()}
        self.assertEqual(before, after)
        self.assertIn("PASS project config", output)
        self.assertIn("PASS OpenSpec root", output)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        for arguments in (["list", "--json"], ["doctor"]):
            self.assertIn(["openspec", str(self.project), arguments], calls)

    def test_project_uses_nearest_openspec_root(self):
        package = self.project / "packages/child"
        (package / "openspec").mkdir(parents=True)
        nested = package / "src"
        nested.mkdir()
        self.write_config(self.config.replace('openspec_root: "openspec"',
                                              'openspec_root: "packages/child/openspec"'))
        self.git("add", ".agents/project.md")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "--quiet", "-m", "nested config")
        self.env["DOCTOR_TEST_OPENROOT"] = str(package)
        self.assertIn("PASS OpenSpec root", self.run_doctor("--project", nested))

    def test_project_requires_git_and_openspec_roots(self):
        self.run_doctor("--project", self.root, success=False)
        shutil.rmtree(self.project / "openspec")
        self.assertIn("FAIL OpenSpec root", self.run_doctor("--project", self.project, success=False))

    def test_project_requires_correct_links(self):
        link = self.agents / "shared"
        target = link.readlink()
        link.unlink()
        with self.subTest(link="shared"):
            self.run_doctor("--project", self.project, success=False)
        link.symlink_to(self.repository / "templates")
        self.run_doctor("--project", self.project, success=False)
        link.unlink()
        link.symlink_to(target)

    def test_project_validates_config_fields_without_echoing_values(self):
        for field in ("project_name", "project_realpath", "main_branch", "expected_remote",
                      "stack", "openspec_root", "quality_gates", "protected_data",
                      "project_constraints", "project_skills"):
            with self.subTest(field=field):
                self.write_config(self.config.replace(field + ":", "other_field:"))
                self.assertIn("FAIL project config", self.run_doctor("--project", self.project, success=False))
        self.write_config(self.config.replace(str(self.project), "/wrong/project"))
        self.assertIn("FAIL project config", self.run_doctor("--project", self.project, success=False))
        self.write_config(self.config.replace('openspec_root: "openspec"', 'openspec_root: "wrong"'))
        self.assertIn("FAIL project config", self.run_doctor("--project", self.project, success=False))
        self.write_config(self.config.replace('project_name: "fixture-project"',
                                              'project_name: "' + self.env["DOCTOR_TEST_SECRET"] + '"'))
        self.run_doctor("--project", self.project, success=False)

    def test_project_runtime_paths_must_be_git_ignored(self):
        for entry in ("/state/\n", "/runs/\n", "/*.lock\n"):
            (self.agents / ".gitignore").write_text("/state/\n/runs/\n/*.lock\n".replace(entry, ""))
            with self.subTest(entry=entry):
                self.assertIn("FAIL runtime ignore", self.run_doctor("--project", self.project, success=False))

    def test_project_rejects_null_or_numeric_required_strings(self):
        for value in ("null", "~", "123", "false"):
            self.write_config(self.config.replace('project_name: "fixture-project"',
                                                  "project_name: " + value))
            with self.subTest(value=value):
                self.assertIn("FAIL project config", self.run_doctor("--project", self.project, success=False))

    def test_sensitive_values_in_untracked_path_names_are_redacted(self):
        for marker in ("TOKEN", "KEY", "SECRET"):
            (self.project / (self.env["DOCTOR_TEST_" + marker] + ".txt")).write_text("private\n")
        self.assertIn("[redacted]", self.run_doctor("--project", self.project))

    def test_escaped_sensitive_untracked_paths_are_redacted_before_json_encoding(self):
        for index, value in enumerate(('credential"quote', "credential\\backslash",
                                       "credential\nnewline", "credential-敏感")):
            self.env["DOCTOR_TEST_SECRET_CASE_" + str(index)] = value
            (self.project / (value + '-"public\\suffix\n终".txt')).write_text("private\n")
        for prefix in ("PASS untracked baseline ", "WARN untracked new "):
            with self.subTest(diagnostic=prefix):
                output = self.run_doctor("--project", self.project)
                labels = [json.loads(line[len(prefix):]) for line in output.splitlines()
                          if line.startswith(prefix)]
                self.assertEqual(labels, ['[redacted]-"public\\suffix\n终".txt'] * 4)
            (self.agents / "state/run.json").write_text(json.dumps({
                "RUN_ID": "run", "STATE": "APPLYING", "UNTRACKED_BASELINE": [],
            }))

    def test_escaped_sensitive_lock_names_are_redacted_before_json_encoding(self):
        identities = (
            ("stale", {"PID": 2147483647}, "WARN stale lock "),
            ("live", {"PID": os.getpid()}, "PASS lock owner present "),
            ("unknown", {}, "WARN lock identity could not be verified "),
        )
        for index, value in enumerate(('credential"quote', "credential\\backslash",
                                       "credential\nnewline", "credential-敏感")):
            self.env["DOCTOR_TEST_SECRET_CASE_" + str(index)] = value
            for kind, identity, prefix in identities:
                (self.agents / (kind + "-" + value + ".lock")).write_text(json.dumps(identity))
        output = self.run_doctor("--project", self.project)
        for kind, identity, prefix in identities:
            with self.subTest(diagnostic=prefix):
                labels = [json.loads(line[len(prefix):]) for line in output.splitlines()
                          if line.startswith(prefix)]
                self.assertEqual(labels, [kind + "-[redacted].lock"] * 4)

    def test_project_tracked_dirty_or_staged_files_need_human(self):
        (self.project / "tracked.txt").write_text("modified\n")
        self.assertIn("NEEDS_HUMAN", self.run_doctor("--project", self.project, success=False))
        self.git("add", "tracked.txt")
        self.assertIn("NEEDS_HUMAN", self.run_doctor("--project", self.project, success=False))

    def test_project_untracked_baseline_is_not_a_failure(self):
        (self.project / "baseline.sqlite").write_text(self.env["DOCTOR_TEST_SECRET"])
        output = self.run_doctor("--project", self.project)
        self.assertIn("baseline.sqlite", output)
        self.assertNotIn("NEEDS_HUMAN", output)

    def test_project_recorded_baseline_distinguishes_new_untracked_paths(self):
        (self.project / "baseline.sqlite").write_text("baseline\n")
        (self.agents / "state/run.json").write_text(json.dumps({
            "RUN_ID": "run", "STATE": "APPLYING", "UNTRACKED_BASELINE": ["baseline.sqlite"],
        }))
        output = self.run_doctor("--project", self.project)
        self.assertIn("baseline", output)
        (self.project / "new.txt").write_text("new\n")
        output = self.run_doctor("--project", self.project)
        self.assertIn("WARN untracked new", output)
        self.assertIn("new.txt", output)

    def test_project_cli_failures_and_invalid_json_are_failures(self):
        for failure in ("list", "doctor", "json"):
            self.env["DOCTOR_TEST_OPENSPEC_FAIL"] = failure
            with self.subTest(failure=failure):
                self.assertIn("FAIL OpenSpec", self.run_doctor("--project", self.project, success=False))

    def test_project_git_failure_is_not_misreported_as_dirty(self):
        self.env["DOCTOR_TEST_GIT_FAIL"] = "diff"
        output = self.run_doctor("--project", self.project, success=False)
        self.assertNotIn("NEEDS_HUMAN", output)

    def test_stale_lock_warns_and_is_never_removed(self):
        lock = self.agents / "workflow.lock"
        lock.write_text(json.dumps({"PID": 2147483647}))
        original = lock.read_bytes()
        self.assertIn("WARN stale lock", self.run_doctor("--project", self.project))
        self.assertEqual(lock.read_bytes(), original)

    def test_live_lock_and_session_mismatch(self):
        lock = self.agents / "workflow.lock"
        lock.write_text(json.dumps({"pid": os.getpid(), "session_id": os.getsid(0)}))
        output = self.run_doctor("--project", self.project)
        self.assertIn("PASS lock", output)
        self.assertNotIn("stale lock", output)
        lock.write_text(json.dumps({"PID": os.getpid(), "SESSION_ID": 2147483647}))
        self.assertIn("WARN stale lock", self.run_doctor("--project", self.project))

    def test_lock_with_unverifiable_identity_warns(self):
        lock = self.agents / "workflow.lock"
        for content in ("not-json", "{}", '{"PID": "unknown"}', '{"SESSION_ID": "session"}'):
            lock.write_text(content)
            with self.subTest(content=content):
                self.assertIn("WARN lock", self.run_doctor("--project", self.project))
                self.assertEqual(lock.read_text(), content)

    def test_invalid_arguments_are_line_oriented_failures(self):
        for arguments in ((), ("--project",), ("--unknown",), ("--global", "extra")):
            with self.subTest(arguments=arguments):
                self.run_doctor(*arguments, success=False)


if __name__ == "__main__":
    unittest.main()
