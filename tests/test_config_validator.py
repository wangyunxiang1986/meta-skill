import importlib.util
import pathlib
import unittest

TMPL = pathlib.Path(__file__).resolve().parents[1] / "engine" / "templates" / "config.py"


def _load():
    spec = importlib.util.spec_from_file_location("gen_config", TMPL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ConfigValidatorTest(unittest.TestCase):
    CONSTRAINTS = {
        "eos_type": {"choices": ["hotqcd2014", "lattice_pce165"], "exclusive_with": []},
        "nsample": {"range": [1, 2000], "exclusive_with": []},
        "fast": {"exclusive_with": ["slow"]},
        "slow": {"exclusive_with": ["fast"]},
    }

    def test_clean_config_passes(self):
        cfg = "[g]\neos_type = hotqcd2014\nnsample = 100\nfast = 1\n"
        self.assertEqual(_load().validate(cfg, self.CONSTRAINTS), [])

    def test_violations_detected(self):
        cfg = "[g]\neos_type = bogus\nnsample = 999999\nfast = 1\nslow = 1\n"
        v = "\n".join(_load().validate(cfg, self.CONSTRAINTS))
        self.assertIn("eos_type", v)
        self.assertIn("nsample", v)
        self.assertIn("mutually exclusive", v)

    def test_inline_comments_are_stripped(self):
        # CLVisc .info files use ';' inline comments (and '#'); a valid value
        # followed by a comment must not be misread as a violation.
        cfg = "[g]\neos_type = hotqcd2014   ; the QCD EOS\nnsample = 100  # oversampling\n"
        self.assertEqual(_load().validate(cfg, self.CONSTRAINTS), [])

    def test_malformed_range_is_ignored_not_crash(self):
        constraints = {"nsample": {"range": [1], "exclusive_with": []}}
        cfg = "[g]\nnsample = 100\n"
        self.assertEqual(_load().validate(cfg, constraints), [])  # skipped, no crash


if __name__ == "__main__":
    unittest.main()
