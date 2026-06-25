import unittest
from engine import generate


def _scan():
    return {"parameters": [
        {"name": "eos", "type": "", "default": None, "choices": ["a", "b"],
         "required": True, "exclusive_group": None, "help": "", "source": "cli.py"},
        {"name": "fast", "type": "", "default": None, "choices": None,
         "required": None, "exclusive_group": 0, "help": "", "source": "cli.py"},
        {"name": "slow", "type": "", "default": None, "choices": None,
         "required": None, "exclusive_group": 0, "help": "", "source": "cli.py"},
        {"name": "nsample", "type": "int", "default": 1, "choices": None,
         "required": None, "exclusive_group": None, "help": "", "source": "cli.py"},
    ]}


class MergeConstraintsTest(unittest.TestCase):
    def test_merge_scanned_and_pack(self):
        k = {"param_constraints": {"nsample": {"range": [1, 2000], "note": "oversampling"}}}
        merged = generate.merge_param_constraints(_scan(), k)
        self.assertEqual(merged["eos"]["choices"], ["a", "b"])
        self.assertTrue(merged["eos"]["required"])
        self.assertEqual(merged["fast"]["exclusive_with"], ["slow"])
        self.assertEqual(merged["slow"]["exclusive_with"], ["fast"])
        self.assertEqual(merged["nsample"]["range"], [1, 2000])

    def test_malformed_range_does_not_crash_render(self):
        scan = {"parameters": [
            {"name": "nsample", "type": "int", "default": 1, "choices": None,
             "required": None, "exclusive_group": None, "help": "", "source": "x"}]}
        md = generate.render_parameters(scan, {"param_constraints": {"nsample": {"range": [1]}}})
        self.assertIn("nsample", md)  # malformed range skipped, no crash

    def test_render_parameters_has_new_columns(self):
        md = generate.render_parameters(_scan(), {"param_constraints":
                                       {"nsample": {"range": [1, 2000]}}})
        self.assertIn("Choices/Range", md)
        self.assertIn("Mutually-exclusive-with", md)
        self.assertIn("choices: a, b", md)
        self.assertIn("range: 1..2000", md)
        self.assertIn("slow", md)  # fast's exclusive partner listed


if __name__ == "__main__":
    unittest.main()
