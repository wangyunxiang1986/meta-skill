import pathlib
import tempfile
import unittest

from engine import scan as scanmod
from engine import generate


class CppEntryDetectionTest(unittest.TestCase):
    def test_detects_cpp_main_with_named_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "main.cpp").write_text(
                '#include "x.h"\n'
                'int main(int argc, char **argv) {\n'
                '    int jobid = atoi(argv[1]);\n'
                '    return 0;\n}\n', encoding="utf-8")
            (root / "Makefile").write_text("EXE=lbt\nall: $(EXE)\n", encoding="utf-8")
            entries = scanmod.detect_cpp_entrypoints(root)
            self.assertTrue(entries)
            e = entries[0]
            self.assertEqual(e["cli_style"], "argv")
            self.assertEqual(e["lang"], "cpp")
            self.assertEqual(e["argv_names"], ["jobid"])
            self.assertEqual(e["argv_required"], 1)
            self.assertEqual(e["run_prefix"], ["./lbt"])

    def test_ignores_cpp_without_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "lib.cpp").write_text("int helper(){return 1;}\n", encoding="utf-8")
            self.assertEqual(scanmod.detect_cpp_entrypoints(root), [])


class CppCommandResolutionTest(unittest.TestCase):
    def test_scan_project_derives_cpp_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "Codes"
            root.mkdir(parents=True)
            (root / "main.cpp").write_text(
                "int main(int argc, char **argv){ int jobid = atoi(argv[1]); }\n",
                encoding="utf-8")
            (root / "Makefile").write_text("EXE=lbt\n", encoding="utf-8")
            scan = scanmod.scan_project(root)
            self.assertIsNotNone(scan["primary_entry"])
            # derived from source + Makefile + pack arg_defaults (jobid example value)
            argv = generate.resolve_command_argv(
                scan, {"arg_map": {}, "arg_defaults": {"jobid": "0"}})
            self.assertEqual(argv, ["./lbt", "0"])


if __name__ == "__main__":
    unittest.main()
