"""Regression checks for validation after installing workspace dependencies."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validate_repository import (
    check_cross_app_boundaries,
    check_forbidden_files,
    check_markdown_links,
)


class RepositoryTraversalTests(unittest.TestCase):
    def test_generated_directories_are_ignored(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for directory in ("node_modules", ".expo", ".git"):
                generated = root / "apps" / "burrow-clock" / directory / "nested"
                generated.mkdir(parents=True)
                (generated / ".env").write_text("placeholder", encoding="utf-8")
                (generated / "README.md").write_text(
                    "[Dependency link](F:/missing.md)\napps/pensieve/private\n",
                    encoding="utf-8",
                )
            self.assertEqual(check_forbidden_files(str(root)), [])
            self.assertEqual(check_markdown_links(str(root)), [])
            self.assertEqual(check_cross_app_boundaries(str(root)), [])

    def test_source_secrets_are_still_reported(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".env").write_text("placeholder", encoding="utf-8")
            self.assertEqual(len(check_forbidden_files(str(root))), 1)

    def test_source_broken_links_are_still_reported(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "README.md").write_text("[Missing](missing.md)", encoding="utf-8")
            self.assertEqual(len(check_markdown_links(str(root))), 1)

    def test_source_boundary_violations_are_still_reported(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = root / "apps" / "burrow-clock"
            app.mkdir(parents=True)
            (app / "source.ts").write_text("import '../pensieve/private';", encoding="utf-8")
            self.assertEqual(len(check_cross_app_boundaries(str(root))), 1)


if __name__ == "__main__":
    unittest.main()
