import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
SCRIPT = REPOSITORY / "scripts" / "link-project.sh"
TEMPLATE = REPOSITORY / "templates" / "project.md"


class LinkProjectTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.project = self.root / "project"
        self.project.mkdir()
        subprocess.run(
            ["git", "init", "--quiet", str(self.project)],
            check=True,
            capture_output=True,
            text=True,
        )

    def run_script(self, *arguments):
        self.assertTrue(SCRIPT.is_file(), f"missing bootstrap script: {SCRIPT}")
        return subprocess.run(
            [str(SCRIPT), *map(str, arguments)],
            cwd=self.root,
            capture_output=True,
            text=True,
        )

    def assert_success(self, result):
        self.assertEqual(
            result.returncode,
            0,
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def assert_links_are_correct(self):
        link = self.project / ".agents" / "shared"
        self.assertTrue(link.is_symlink(), f"{link} is not a symlink")
        self.assertEqual(link.resolve(), (REPOSITORY / "agents/shared").resolve())
        self.assertFalse((self.project / ".agents" / "team").exists())

    def test_dry_run_reports_success_without_writing(self):
        marker = self.project / "keep.txt"
        marker.write_text("unchanged\n")

        result = self.run_script("--dry-run", self.project)

        self.assert_success(result)
        self.assertFalse((self.project / ".agents").exists())
        self.assertEqual(marker.read_text(), "unchanged\n")

    def test_first_install_creates_only_project_agent_files(self):
        marker = self.project / "keep.txt"
        marker.write_text("unchanged\n")

        result = self.run_script(self.project)

        self.assert_success(result)
        agents = self.project / ".agents"
        self.assertEqual(
            sorted(path.name for path in agents.iterdir()),
            [".gitignore", "project.md", "runs", "shared", "state"],
        )
        self.assert_links_are_correct()
        self.assertTrue((agents / "state").is_dir())
        self.assertTrue((agents / "runs").is_dir())
        self.assertTrue(TEMPLATE.is_file())
        self.assertEqual((agents / "project.md").read_text(), TEMPLATE.read_text())
        self.assertEqual(marker.read_text(), "unchanged\n")

    def test_second_install_is_idempotent(self):
        first = self.run_script(self.project)
        self.assert_success(first)
        agents = self.project / ".agents"
        before = {
            "children": sorted(path.name for path in agents.iterdir()),
            "project": (agents / "project.md").read_text(),
            "gitignore": (agents / ".gitignore").read_text(),
            "shared": os.readlink(agents / "shared"),
        }

        second = self.run_script(self.project)

        self.assert_success(second)
        self.assertEqual(
            {
                "children": sorted(path.name for path in agents.iterdir()),
                "project": (agents / "project.md").read_text(),
                "gitignore": (agents / ".gitignore").read_text(),
                "shared": os.readlink(agents / "shared"),
            },
            before,
        )

    def test_existing_project_file_is_preserved(self):
        agents = self.project / ".agents"
        agents.mkdir()
        project_file = agents / "project.md"
        project_file.write_text("project-specific content\n")

        result = self.run_script(self.project)

        self.assert_success(result)
        self.assertEqual(project_file.read_text(), "project-specific content\n")
        self.assert_links_are_correct()

    def test_regular_shared_directory_is_refused_without_partial_install(self):
        agents = self.project / ".agents"
        shared = agents / "shared"
        shared.mkdir(parents=True)
        sentinel = shared / "keep.txt"
        sentinel.write_text("keep\n")

        result = self.run_script(self.project)

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(shared.is_dir())
        self.assertFalse(shared.is_symlink())
        self.assertEqual(sentinel.read_text(), "keep\n")
        self.assertEqual(sorted(path.name for path in agents.iterdir()), ["shared"])

    def test_wrong_shared_symlink_is_refused_without_partial_install(self):
        agents = self.project / ".agents"
        agents.mkdir()
        wrong_target = self.root / "wrong-shared"
        wrong_target.mkdir()
        shared = agents / "shared"
        shared.symlink_to(wrong_target)

        result = self.run_script(self.project)

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(shared.is_symlink())
        self.assertEqual(shared.resolve(), wrong_target.resolve())
        self.assertEqual(sorted(path.name for path in agents.iterdir()), ["shared"])

    def test_gitignore_contains_exactly_the_three_runtime_entries(self):
        result = self.run_script(self.project)

        self.assert_success(result)
        self.assertEqual(
            (self.project / ".agents" / ".gitignore").read_text(),
            "/state/\n/runs/\n/*.lock\n",
        )

    def test_non_git_target_is_refused_without_writing(self):
        not_a_repository = self.root / "not-a-repository"
        not_a_repository.mkdir()

        result = self.run_script(not_a_repository)

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((not_a_repository / ".agents").exists())

    def test_exactly_one_project_path_is_required(self):
        missing = self.run_script()
        extra = self.run_script(self.project, self.root)

        self.assertNotEqual(missing.returncode, 0)
        self.assertNotEqual(extra.returncode, 0)
        self.assertFalse((self.project / ".agents").exists())


if __name__ == "__main__":
    unittest.main()
