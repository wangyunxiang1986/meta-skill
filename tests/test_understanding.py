import unittest

from engine import understanding


class UnderstandingTest(unittest.TestCase):
    def _scan(self):
        return {
            "project_root": "/x", "git": {"commit": "abc", "describe": "v1"},
            "directories": ["pyvisc"], "dependencies": ["OpenCL"],
            "entrypoints": [{"path": "pyvisc/CLVisc.py", "purpose": "CLI entry (argv)",
                             "cli_style": "argv", "argv_names": ["cfg", "cent"]}],
            "parameters": [{"name": "TFRZ", "type": "float", "default": "0.137",
                            "help": "", "source": "hydro.info"}],
            "output_files": [{"name": "hypersf.dat", "source": "pyvisc/visc.py"}],
        }

    def test_with_pack_uses_meanings(self):
        pack = {"name": "clvisc", "knowledge": {
            "param_meaning": {"TFRZ": "freeze-out temperature"},
            "output_meaning": {"hypersf.dat": "freeze-out surface"}}}
        md = understanding.render_project_understanding(self._scan(), pack)
        self.assertIn("clvisc", md)
        self.assertIn("freeze-out temperature", md)
        self.assertIn("source-derived", md.lower())

    def test_generic_points_to_model_gaps(self):
        md = understanding.render_project_understanding(self._scan(), None)
        self.assertIn("model-gaps", md)
        self.assertIn("TFRZ", md)


if __name__ == "__main__":
    unittest.main()
