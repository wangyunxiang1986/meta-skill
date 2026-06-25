import unittest
import pathlib
import tempfile

from engine import generate


class GenRefsTest(unittest.TestCase):
    def _scan(self):
        return {
            "project_root": "/x",
            "git": {},
            "parameters": [{"name": "alpha", "type": "float", "default": "0.5",
                            "choices": None, "help": "", "source": "run.py"}],
            "output_files": [{"name": "result.dat", "source": "pkg/w.py"}],
            "entrypoints": [], "directories": [], "file_counts": {}, "dependencies": [],
        }

    def test_meanings_from_pack(self):
        knowledge = {"param_meaning": {"alpha": "a knob"},
                     "output_meaning": {"result.dat": "the result"}}
        params_md = generate.render_parameters(self._scan(), knowledge)
        outputs_md = generate.render_outputs(self._scan(), knowledge)
        self.assertIn("a knob", params_md)
        self.assertIn("the result", outputs_md)

    def test_generic_fallback_blank_meaning(self):
        params_md = generate.render_parameters(self._scan(), None)
        self.assertIn("alpha", params_md)
        outputs_md = generate.render_outputs(self._scan(), None)
        self.assertIn("result.dat", outputs_md)

    def test_references_redact_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            root.mkdir()
            scan = self._scan()
            scan["project_root"] = str(root)
            scan["parameters"][0]["source"] = str(root / "pkg" / "run.py")
            scan["parameters"][0]["default"] = str(root / "results" / "event0")
            scan["output_files"][0]["source"] = str(root / "pkg" / "w.py")
            scan["readme_commands"] = [f"python {root}/pkg/run.py --x"]
            out = pathlib.Path(tmp) / "skill"
            generate.generate(scan, None, out)
            combined = "\n".join(
                p.read_text(encoding="utf-8")
                for p in (out / "references").glob("*")
                if p.is_file()
            )
            self.assertNotIn(str(root), combined)
            self.assertIn("<PROJECT_ROOT>/pkg/run.py", combined)
            self.assertIn("<PROJECT_ROOT>/results/event0", combined)
            self.assertIn("<PROJECT_ROOT>/pkg/w.py", combined)
            self.assertTrue((out / "references" / "project-profile.json").exists())
            self.assertTrue((out / "references" / "project-understanding.md").exists())

    def test_external_absolute_defaults_are_redacted(self):
        scan = self._scan()
        scan["project_root"] = "/project/root"
        scan["parameters"][0]["default"] = "/home/alice/trento/events/event0.dat"
        md = generate.render_parameters(scan, None, project_root="/project/root")
        self.assertNotIn("/home/alice", md)
        self.assertIn("<LOCAL_PATH>/trento/events/event0.dat", md)


if __name__ == "__main__":
    unittest.main()
