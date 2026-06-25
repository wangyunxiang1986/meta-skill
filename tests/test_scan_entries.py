import pathlib
import tempfile
import unittest

from engine import scan


class EntryScanTest(unittest.TestCase):
    def test_detects_argparse_and_argv_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            pkg = root / "pkg"
            pkg.mkdir()
            (pkg / "cli_args.py").write_text(
                "import argparse\np=argparse.ArgumentParser()\np.parse_args()\n", encoding="utf-8")
            (pkg / "cli_pos.py").write_text(
                "import sys\ncfg=sys.argv[1]\nn=int(sys.argv[2])\n", encoding="utf-8")
            entries = scan.detect_entrypoints(root, py_dirs=["pkg"])
            by = {e["path"].split('/')[-1]: e for e in entries}
            self.assertEqual(by["cli_args.py"]["cli_style"], "argparse")
            self.assertEqual(by["cli_pos.py"]["cli_style"], "argv")
            self.assertEqual(by["cli_pos.py"]["argv_names"], ["cfg", "n"])
            self.assertNotIn("runs_hydro", by["cli_pos.py"])

    def test_detects_nested_python_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            nested = root / "bin" / "drivers"
            nested.mkdir(parents=True)
            (nested / "main.py").write_text(
                "import sys\narg = sys.argv[1]\n", encoding="utf-8")
            entries = scan.detect_entrypoints(root, py_dirs=["bin"])
            self.assertEqual(entries[0]["path"], "bin/drivers/main.py")


if __name__ == "__main__":
    unittest.main()
