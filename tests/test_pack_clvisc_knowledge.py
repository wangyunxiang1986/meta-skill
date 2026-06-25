import pathlib
import unittest

import yaml

KN = pathlib.Path(__file__).resolve().parents[1] / "packs" / "clvisc" / "knowledge.yaml"


class ClviscKnowledgeTest(unittest.TestCase):
    def test_required_sections(self):
        kn = yaml.safe_load(KN.read_text(encoding="utf-8"))
        self.assertIn("ETAOS_YMIN", kn["param_meaning"])
        self.assertIn("hypersf.dat", kn["output_meaning"])
        prof = kn["run_profiles"]["minimal"]
        # command is NOT hardcoded in the pack; only an arg_map driver spec
        self.assertNotIn("command_argv", prof)
        self.assertNotIn("command_template", prof)
        self.assertIn("config", prof["driver"]["arg_map"])
        self.assertEqual(prof["tier1_output"], "hypersf.dat")
        self.assertEqual(prof["tier2_observable"], "dNchdeta")

    def test_has_description(self):
        kn = yaml.safe_load(KN.read_text(encoding="utf-8"))
        self.assertIn("description", kn)
        self.assertTrue(kn["description"].strip())


if __name__ == "__main__":
    unittest.main()
