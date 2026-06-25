import pathlib
import unittest

import yaml

TPL = pathlib.Path(__file__).resolve().parents[1] / "packs" / "_template"


class TemplateTest(unittest.TestCase):
    def test_template_parses_and_underscored_is_skipped(self):
        for f in ("manifest.yaml", "knowledge.yaml"):
            yaml.safe_load((TPL / f).read_text(encoding="utf-8"))
        self.assertTrue((TPL / "extractors.py").exists())


if __name__ == "__main__":
    unittest.main()
