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
        # _join_and grammar (Oxford comma + "and") and the e.g. clause are pinned:
        self.assertIn("run it, edit its parameters, and analyze its outputs", d)
        self.assertIn(", e.g. scan coupling", d)        # human-phrasing trigger, with clause prefix

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
        pack = _pack(description='He said "hi"\nand a path C:\\x\\')
        d = generate.render_skill_description(scan, pack)
        self.assertNotIn('"', d)                          # double quotes neutralized
        self.assertNotIn("\n", d)                         # single line
        self.assertNotIn("\\", d)                         # backslash neutralized (no escape introducer)

    def test_two_verb_join(self):
        # exercises _join_and's 2-item branch (run it + edit its parameters, no outputs)
        scan = _scan(parameters=[{"name": "a"}], output_files=[])
        d = generate.render_skill_description(scan, _pack(description="X."))
        self.assertIn("run it and edit its parameters", d)
        self.assertNotIn("analyze its outputs", d)

    def test_wired_into_skill_md(self):
        scan = _scan(parameters=[{"name": "a"}])
        pack = _pack(description="DemoCode: toy.")
        md = generate.render_skill_md(scan, pack)
        self.assertIn("DemoCode: toy", md)
        self.assertNotIn("Version-specific skill for this scanned checkout", md)


class EvalSeedTest(unittest.TestCase):
    def test_from_demos(self):
        pack = _pack(demos=[
            {"title": "t1", "intent": "run the minimal case", "args": {"cent": "0_5"}},
            {"title": "t2", "intent": "scan the coupling"},
        ])
        out = generate.render_evals(_scan(), pack)
        self.assertEqual(out["skill_name"], generate.generated_skill_name(_scan(), pack))
        self.assertEqual(len(out["evals"]), 2)
        e0 = out["evals"][0]
        self.assertIn("run the minimal case", e0["prompt"])
        self.assertIn("cent=0_5", e0["prompt"])           # args surfaced
        self.assertEqual(e0["files"], [])
        self.assertTrue(e0["expected_output"])

    def test_from_intent_rules_when_no_demos(self):
        pack = _pack(intent_rules=[{"match": ["scan coupling"]}])
        out = generate.render_evals(_scan(), pack)
        self.assertEqual(len(out["evals"]), 1)
        self.assertIn("scan coupling", out["evals"][0]["prompt"])

    def test_generic_when_no_pack(self):
        out = generate.render_evals(_scan(), None)
        self.assertEqual(len(out["evals"]), 1)
        self.assertIn("minimal example", out["evals"][0]["prompt"])

    def test_generate_writes_evals_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "src"
            root.mkdir()
            out = pathlib.Path(tmp) / "skill"
            generate.generate(_scan(project_root=str(root)), None, out)
            ev = out / "evals" / "evals.json"
            self.assertTrue(ev.exists())
            data = json.loads(ev.read_text(encoding="utf-8"))
            self.assertIn("skill_name", data)
            self.assertTrue(data["evals"])

    def test_skill_md_points_to_skill_creator(self):
        md = generate.render_skill_md(_scan(), None)
        self.assertIn("Evaluating & Improving", md)
        self.assertIn("skill-creator", md)
        self.assertIn("evals/evals.json", md)

    def test_evals_in_generated_files(self):
        self.assertIn("evals/evals.json", generate._GENERATED_FILES)


if __name__ == "__main__":
    unittest.main()
