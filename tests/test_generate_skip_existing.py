import pathlib
import tempfile
import unittest

from engine import generate


def _minimal_scan(root):
    return {
        "project_root": str(root),
        "git": {},
        "parameters": [],
        "output_files": [],
        "entrypoints": [],
        "directories": [],
        "file_counts": {},
        "dependencies": [],
    }


class SkillExistsTest(unittest.TestCase):
    def test_false_when_no_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(generate.skill_exists(pathlib.Path(tmp) / "skill"))

    def test_false_when_skill_md_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "skill"
            out.mkdir()
            (out / "SKILL.md").write_text("", encoding="utf-8")
            self.assertFalse(generate.skill_exists(out))

    def test_true_when_skill_md_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "skill"
            out.mkdir()
            (out / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
            self.assertTrue(generate.skill_exists(out))


class ComposeTest(unittest.TestCase):
    def test_generates_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            root.mkdir(parents=True)
            out = pathlib.Path(tmp) / "skill"
            report = generate.compose(_minimal_scan(root), None, out)
            self.assertFalse(report["skipped"])
            self.assertTrue((out / "SKILL.md").exists())

    def test_skips_when_existing_skill_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            root.mkdir(parents=True)
            out = pathlib.Path(tmp) / "skill"
            out.mkdir()
            sentinel = "---\nname: already-here\n---\nSENTINEL\n"
            (out / "SKILL.md").write_text(sentinel, encoding="utf-8")
            report = generate.compose(_minimal_scan(root), None, out)
            self.assertTrue(report["skipped"])
            # existing skill is left untouched
            self.assertEqual((out / "SKILL.md").read_text(encoding="utf-8"), sentinel)

    def test_defers_when_code_ships_skill(self):
        # The code already ships a hand-authored skill -> meta-skill must not
        # generate a competing (thinner) one; it defers by default.
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            root.mkdir(parents=True)
            out = pathlib.Path(tmp) / "skill"
            scan = _minimal_scan(root)
            scan["existing_skills"] = [{"name": "run-hydro",
                                        "path": ".claude/skills/run-hydro/SKILL.md",
                                        "description": "ships already"}]
            report = generate.compose(scan, None, out)
            self.assertTrue(report["skipped"])
            self.assertIn("ship", report["reason"])
            self.assertEqual(report["existing_skills"][0]["name"], "run-hydro")
            self.assertFalse((out / "SKILL.md").exists())

    def test_force_generates_despite_code_shipped_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            root.mkdir(parents=True)
            out = pathlib.Path(tmp) / "skill"
            scan = _minimal_scan(root)
            scan["existing_skills"] = [{"name": "x", "path": "skills/x/SKILL.md",
                                        "description": ""}]
            report = generate.compose(scan, None, out, force=True)
            self.assertFalse(report["skipped"])
            self.assertTrue((out / "SKILL.md").exists())

    def test_force_regenerates_over_existing_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            root.mkdir(parents=True)
            out = pathlib.Path(tmp) / "skill"
            out.mkdir()
            (out / "SKILL.md").write_text("---\nname: x\n---\nSENTINEL\n", encoding="utf-8")
            report = generate.compose(_minimal_scan(root), None, out, force=True)
            self.assertFalse(report["skipped"])
            self.assertNotIn("SENTINEL", (out / "SKILL.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
