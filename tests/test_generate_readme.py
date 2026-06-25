import unittest
from engine import generate


def _scan(**kw):
    base = {"readme_path": None, "primary_entry": None, "readme_commands": [],
            "parameters": [], "output_files": [], "entrypoints": [],
            "build_targets": [], "build_files": [], "dependencies": [],
            "project_root": "/tmp/Demo"}
    base.update(kw)
    return base


class ReadmeStatusTest(unittest.TestCase):
    def test_missing_when_no_readme(self):
        self.assertEqual(generate.readme_status(_scan(readme_path=None)), "missing")

    def test_problematic_when_readme_arg_count_stale(self):
        scan = _scan(
            readme_path="README.md",
            primary_entry={"path": "run.py", "argv_names": ["a", "b", "c"],
                           "argv_required": 3},
            readme_commands=["python run.py X"])   # README shows 1 positional, code needs 3
        self.assertEqual(generate.readme_status(scan), "problematic")

    def test_ok_when_readme_present_and_consistent(self):
        scan = _scan(
            readme_path="README.md",
            primary_entry={"path": "run.py", "argv_names": ["a"], "argv_required": 1},
            readme_commands=["python run.py X"])
        self.assertEqual(generate.readme_status(scan), "ok")


if __name__ == "__main__":
    unittest.main()
