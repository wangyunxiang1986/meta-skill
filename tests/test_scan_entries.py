import pathlib
import tempfile
import unittest

from engine import scan


class PrimaryEntryTest(unittest.TestCase):
    def _entry(self, path, argv=0):
        return {"path": path, "cli_style": "argv",
                "argv_names": ["a%d" % i for i in range(argv)], "reads_config": False}

    def test_auxiliary_dir_demoted_even_with_more_argv(self):
        # A helper main() under test/ that parses more argv must NOT outrank the real
        # src/ entry that exposes none (the TRENTo woods-saxon vs src/trento.cxx case).
        entries = [self._entry("src/main.cxx", argv=0),
                   self._entry("test/helper/gen.cxx", argv=3)]
        primary = scan.primary_entrypoint(entries, readme_commands=[])
        self.assertEqual(primary["path"], "src/main.cxx")

    def test_all_auxiliary_still_picks_one(self):
        # If every candidate is auxiliary, demotion is a no-op; still return a driver.
        entries = [self._entry("tests/a.py", argv=1), self._entry("tests/b.py", argv=2)]
        primary = scan.primary_entrypoint(entries, readme_commands=[])
        self.assertEqual(primary["path"], "tests/b.py")   # more argv wins within same class

    def test_is_auxiliary_path(self):
        self.assertTrue(scan._is_auxiliary_path("test/x.cxx"))
        self.assertTrue(scan._is_auxiliary_path("a/examples/y.py"))
        self.assertFalse(scan._is_auxiliary_path("src/main.cxx"))
        self.assertFalse(scan._is_auxiliary_path("pyvisc/CLVisc.py"))


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
