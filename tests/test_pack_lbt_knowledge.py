import pathlib
import unittest

import yaml

KN = pathlib.Path(__file__).resolve().parents[1] / "packs" / "lbt" / "knowledge.yaml"


class LbtKnowledgeTest(unittest.TestCase):
    def test_required_sections(self):
        kn = yaml.safe_load(KN.read_text(encoding="utf-8"))
        self.assertIn("alphas", kn["param_meaning"])
        self.assertIn("Kradiation", kn["param_meaning"])
        self.assertIn("positive.dat", kn["output_meaning"])
        prof = kn["run_profiles"]["minimal"]
        # command is NOT hardcoded in the pack; only an arg_map driver spec
        self.assertNotIn("command_argv", prof)
        self.assertNotIn("command_template", prof)
        self.assertEqual(prof["tier1_output"], "positive.dat")
        self.assertEqual(prof["tier2_observable"], "dNdpT_parton")


if __name__ == "__main__":
    unittest.main()
