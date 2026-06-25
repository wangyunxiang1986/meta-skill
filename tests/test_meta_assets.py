import pathlib
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


class MetaAssetsTest(unittest.TestCase):
    def test_openai_yaml_parses(self):
        data = yaml.safe_load((ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8"))
        self.assertIn("interface", data)

    def test_output_contract_exists(self):
        text = (ROOT / "references" / "scientific-package-output-contract.md").read_text(encoding="utf-8")
        self.assertIn("verification-report.md", text)

    def test_readme_matches_six_stage_framework(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("three main modules", text)
        self.assertIn("six-step loop", text)
        self.assertIn("iterate generated skill or knowledge pack", text)
        self.assertIn("not installed automatically", text)
        self.assertNotIn("the 3-step agent workflow", text)


if __name__ == "__main__":
    unittest.main()
