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

    def test_prepare_has_grid_consistency_guard(self):
        # prepare must verify bulk3d.dat record count vs the LBTinput hydro grid,
        # so a mismatched bulk3D fails loudly instead of silently misreading it.
        kn = yaml.safe_load(KN.read_text(encoding="utf-8"))
        prep = " ".join(kn["run_profiles"]["minimal"]["prepare"])
        self.assertIn("bulk3d.dat", prep)
        self.assertIn("nxhydro", prep)
        self.assertIn("grid mismatch", prep)

    def test_has_description(self):
        kn = yaml.safe_load(KN.read_text(encoding="utf-8"))
        self.assertIn("description", kn)
        self.assertTrue(kn["description"].strip())


if __name__ == "__main__":
    unittest.main()
