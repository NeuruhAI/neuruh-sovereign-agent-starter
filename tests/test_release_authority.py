import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReleaseAuthorityTests(unittest.TestCase):
    def test_release_requires_same_repo_push_ci(self):
        workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        self.assertIn("github.event.workflow_run.event == 'push'", workflow)
        self.assertIn("github.event.workflow_run.head_repository.full_name == github.repository", workflow)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", workflow)


if __name__ == "__main__":
    unittest.main()
