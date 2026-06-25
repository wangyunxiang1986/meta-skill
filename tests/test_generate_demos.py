import unittest
from engine import generate


def _scan():
    return {"primary_entry": {"path": "pyvisc/CLVisc.py",
                              "argv_names": ["fconfig", "cent", "gpu", "start_id", "end_id"],
                              "argv_required": 5},
            "parameters": [], "entrypoints": [], "readme_commands": []}


class DemosTest(unittest.TestCase):
    def test_demos_baseline_and_curated(self):
        k = {
            "run_profiles": {"minimal": {"driver": {
                "arg_map": {"config": ["fconfig", "config", "info"],
                            "cent": ["cent"], "gpu": ["gpu"]},
                "arg_defaults": {"start_id": "0", "end_id": "1"}}}},
            "demos": [{"title": "most-central spectra",
                       "intent": "0-5% Au+Au dNch/deta",
                       "args": {"cent": "0_5", "gpu": "0"}}],
        }
        md = generate.render_demos(_scan(), k)
        self.assertIn("# Demos", md)
        self.assertIn("derived baseline", md)
        self.assertIn("most-central spectra", md)
        self.assertIn("0-5% Au+Au dNch/deta", md)
        self.assertIn("0_5", md)              # demo arg substituted

    def test_demos_generic_when_no_command(self):
        md = generate.render_demos({"primary_entry": None, "parameters": [],
                                    "entrypoints": [], "readme_commands": []}, None)
        self.assertIn("generic skill", md)


if __name__ == "__main__":
    unittest.main()
