import pathlib
import json
import tempfile
import unittest

from engine import generate, pack_loader
from engine import scan as scanmod

FIX = pathlib.Path(__file__).resolve().parent / "fixtures" / "packs"


class GenFullTest(unittest.TestCase):
    def test_generate_with_pack_and_extractors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            (root / "pkg").mkdir(parents=True)
            (root / "marker.txt").write_text("x", encoding="utf-8")
            (root / "pkg" / "run.py").write_text(
                "import argparse\np=argparse.ArgumentParser()\n"
                "p.add_argument('--alpha', default=0.5)\np.parse_args()\n", encoding="utf-8")
            scan = scanmod.scan_project(root)
            pack = pack_loader.select_pack(FIX, scan, root)
            out = pathlib.Path(tmp) / "skill"
            generate.generate(scan, pack, out)
            skill_md = (out / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("name: demo-proj", skill_md)
            for marker in ("## What This Program Does", "## Workflow",
                           "## Scripts", "## Validation Status", "## If Blocked"):
                self.assertIn(marker, skill_md)
            self.assertTrue((out / "references" / "parameters.md").exists())
            self.assertTrue((out / "references" / "verified-runs.md").exists())
            self.assertTrue((out / "references" / "blocked-runs.md").exists())
            for script in ("config.py", "run.py", "analysis.py", "visualize.py"):
                self.assertTrue((out / "scripts" / script).exists(), script)
            self.assertTrue((out / "scripts" / "extractors.py").exists())
            self.assertIn("alpha", (out / "references" / "parameters.md").read_text(encoding="utf-8"))
            profile = json.loads((out / "scripts" / "run_profile.json").read_text(encoding="utf-8"))
            self.assertEqual(profile["command_argv"], ["python", "run.py", "{config}"])

    def test_generate_generic_no_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            root.mkdir(parents=True)
            (root / "cli.py").write_text("import sys\na=sys.argv[1]\n", encoding="utf-8")
            scan = scanmod.scan_project(root)
            out = pathlib.Path(tmp) / "skill"
            generate.generate(scan, None, out)
            skill_md = (out / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("name: generated-project-skill-proj", skill_md)
            self.assertFalse((out / "scripts" / "extractors.py").exists())

    def test_regenerate_removes_stale_pack_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            root.mkdir(parents=True)
            scan = {
                "project_root": str(root),
                "git": {},
                "parameters": [],
                "output_files": [],
                "entrypoints": [],
                "directories": [],
                "file_counts": {},
                "dependencies": [],
            }
            out = pathlib.Path(tmp) / "skill"
            pack = {"name": "demo", "knowledge": {"run_profiles": {"minimal": {
                "command_template": "python run.py", "tier1_output": "x.dat"}}},
                "extractors_path": str(pathlib.Path(__file__).resolve().parents[1] / "packs" / "_template" / "extractors.py")}
            generate.generate(scan, pack, out)
            self.assertTrue((out / "scripts" / "extractors.py").exists())
            self.assertTrue((out / "scripts" / "run_profile.json").exists())
            generate.generate(scan, None, out)
            self.assertFalse((out / "scripts" / "extractors.py").exists())
            self.assertFalse((out / "scripts" / "run_profile.json").exists())
            self.assertFalse((out / "scripts" / "run_launcher.py").exists())

    def test_generated_name_includes_git_describe(self):
        scan = {
            "project_root": "/tmp/My_Project",
            "git": {"describe": "v1.2-dirty"},
            "parameters": [],
            "output_files": [],
            "entrypoints": [],
            "directories": [],
            "file_counts": {},
            "dependencies": [],
        }
        name = generate.generated_skill_name(scan, {"name": "clvisc"})
        self.assertEqual(name, "clvisc-my-project-v1-2-dirty")

    def test_generate_report_returns_actual_skill_name(self):
        scan = {
            "project_root": "/tmp/My_Project",
            "git": {"describe": "abc123"},
            "parameters": [],
            "output_files": [],
            "entrypoints": [],
            "directories": [],
            "file_counts": {},
            "dependencies": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            report = generate.generate(scan, None, pathlib.Path(tmp) / "skill")
        self.assertEqual(report["name"], "generated-project-skill-my-project-abc123")


if __name__ == "__main__":
    unittest.main()
