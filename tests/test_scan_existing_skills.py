import pathlib
import tempfile
import unittest

from engine import scan as scanmod


def _mk_skill(base, relpath, name, desc):
    d = base / relpath
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\n# {name}\n", encoding="utf-8")
    return d


class DetectExistingSkillsTest(unittest.TestCase):
    def test_detects_skills_under_skills_dirs(self):
        # Both the .claude/skills/<name>/ convention and a project-specific
        # location like LBTskills/<name>/ must be found.
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            _mk_skill(root, ".claude/skills/run-hydro", "run-hydro", "run the hydro pipeline")
            _mk_skill(root, "LBTskills/LBTmodel", "LBTmodel", "core LBT transport")
            found = scanmod.detect_existing_skills(root)
            self.assertEqual({s["name"] for s in found}, {"run-hydro", "LBTmodel"})
            descs = {s["name"]: s["description"] for s in found}
            self.assertEqual(descs["run-hydro"], "run the hydro pipeline")

    def test_ignores_skill_md_not_under_skills_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            d = root / "docs"
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text("---\nname: stray\n---\n", encoding="utf-8")
            self.assertEqual(scanmod.detect_existing_skills(root), [])

    def test_ignores_junk_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            _mk_skill(root, ".git/skills/x", "x", "junk")
            self.assertEqual(scanmod.detect_existing_skills(root), [])

    def test_excludes_our_own_generated_skill(self):
        # A generated skill carries references/project-profile.json next to
        # SKILL.md; it is OUR output, not a code-shipped skill, so exclude it.
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            d = _mk_skill(root, ".claude/skills/generated", "generated", "ours")
            (d / "references").mkdir()
            (d / "references" / "project-profile.json").write_text("{}", encoding="utf-8")
            self.assertEqual(scanmod.detect_existing_skills(root), [])

    def test_scan_project_populates_existing_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "main.py").write_text("import sys\nx = sys.argv[1]\n", encoding="utf-8")
            _mk_skill(root, "LBTskills/foo", "foo", "a shipped skill")
            scan = scanmod.scan_project(root)
            self.assertIn("existing_skills", scan)
            self.assertEqual(scan["existing_skills"][0]["name"], "foo")


if __name__ == "__main__":
    unittest.main()
