import json
import pathlib
import tempfile
import unittest

from engine import generate


def _scan(**kw):
    base = {"project_root": "/tmp/FooSolver", "readme_path": None,
            "primary_entry": None, "parameters": [], "output_files": [],
            "entrypoints": [], "readme_commands": [], "build_files": [],
            "build_targets": [], "dependencies": [], "git": {},
            "directories": [], "file_counts": {}}
    base.update(kw)
    return base


def _pack(_name="demo", **knowledge):
    return {"name": _name, "knowledge": knowledge}


class TriggerDescriptionTest(unittest.TestCase):
    def test_pack_description_verbs_and_triggers(self):
        scan = _scan(parameters=[{"name": "a"}], output_files=[{"name": "out.dat"}])
        pack = _pack(description="DemoCode: a toy transport model.",
                     intent_rules=[{"match": ["scan coupling", "turn off radiation"]}])
        d = generate.render_skill_description(scan, pack)
        self.assertIn("DemoCode: a toy transport model", d)
        self.assertIn("for this scanned checkout of demo", d)   # preposition present (grammar)
        self.assertIn("run it", d)
        self.assertIn("edit its parameters", d)
        self.assertIn("analyze its outputs", d)
        self.assertIn("scan coupling", d)               # human-phrasing trigger

    def test_no_pack_noun_phrase_and_scan_verbs(self):
        scan = _scan(project_root="/tmp/FooSolver",
                     primary_entry={"path": "main.py"},
                     parameters=[], output_files=[])      # nothing to configure/analyze
        d = generate.render_skill_description(scan, None)
        self.assertIn("FooSolver", d)
        self.assertIn("main.py", d)
        self.assertIn("run it", d)
        self.assertNotIn("edit its parameters", d)        # scan found no parameters
        self.assertNotIn("analyze its outputs", d)        # scan found no outputs
        self.assertNotIn(", e.g.", d)                     # no intent_rules -> no trigger clause
        self.assertNotIn("Version-specific skill for this scanned checkout", d)

    def test_yaml_single_line_safe(self):
        scan = _scan(parameters=[{"name": "a"}])
        pack = _pack(description='He said "hi"\nand more.')
        d = generate.render_skill_description(scan, pack)
        self.assertNotIn('"', d)                          # double quotes neutralized
        self.assertNotIn("\n", d)                         # single line

    def test_wired_into_skill_md(self):
        scan = _scan(parameters=[{"name": "a"}])
        pack = _pack(description="DemoCode: toy.")
        md = generate.render_skill_md(scan, pack)
        self.assertIn("DemoCode: toy", md)
        self.assertNotIn("Version-specific skill for this scanned checkout", md)


if __name__ == "__main__":
    unittest.main()
