import pathlib
import tempfile
import unittest

from engine import scan


class ParamScanTest(unittest.TestCase):
    def test_argparse_and_ini_params(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "run.py").write_text(
                "import argparse\n"
                "p = argparse.ArgumentParser()\n"
                "p.add_argument('--alpha', type=float, default=0.5, help='knob')\n"
                "p.parse_args()\n", encoding="utf-8")
            (root / "in.ini").write_text("[s]\nbeta = 3 ; note\n", encoding="utf-8")
            params = scan.collect_parameters(root, ["run.py"], ["in.ini"])
            names = {p["name"] for p in params}
            self.assertIn("alpha", names)
            self.assertIn("beta", names)


if __name__ == "__main__":
    unittest.main()
