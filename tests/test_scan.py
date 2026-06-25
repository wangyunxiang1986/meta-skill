import pathlib
import tempfile
import unittest

from engine import scan


class ScanFilesTest(unittest.TestCase):
    def _fixture(self, root: pathlib.Path):
        (root / "src").mkdir()
        (root / "src" / "main.cpp").write_text("int main(){}", encoding="utf-8")
        (root / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.0)\n", encoding="utf-8")
        (root / "config.yaml").write_text("a: 1\n", encoding="utf-8")
        (root / "README.md").write_text("demo package\n", encoding="utf-8")

    def test_scan_files_classifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            self._fixture(root)
            result = scan.scan_files(root)
            self.assertIn("CMakeLists.txt", " ".join(result["build_files"]))
            self.assertTrue(any(p.endswith(".yaml") for p in result["config_files"]))
            self.assertTrue(any("main.cpp" in p for p in result["source"]))
            self.assertTrue(result["readme_path"])


class EffectiveRootTest(unittest.TestCase):
    def test_descends_single_wrapper_dir(self):
        # A checkout where the real project sits one level under an otherwise
        # empty wrapper dir (e.g. an unzipped archive: wrapper/Project/pyvisc/...).
        with tempfile.TemporaryDirectory() as tmp:
            wrapper = pathlib.Path(tmp)
            proj = wrapper / "Project"
            (proj / "pyvisc").mkdir(parents=True)
            (proj / "pyvisc" / "run.py").write_text(
                "import sys\ncfg = sys.argv[1]\n", encoding="utf-8")
            (proj / "README.md").write_text("# Project\n", encoding="utf-8")
            # the entrypoint two levels below the wrapper must still be found
            self.assertEqual(scan._effective_root(wrapper), proj)
            sc = scan.scan_project(wrapper)
            self.assertEqual((sc.get("primary_entry") or {}).get("path"), "pyvisc/run.py")

    def test_does_not_descend_when_root_has_signal(self):
        # If the root itself carries project signal, stay put (don't over-descend).
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "run.py").write_text("import sys\nx = sys.argv[1]\n", encoding="utf-8")
            (root / "sub").mkdir()
            self.assertEqual(scan._effective_root(root), root)

    def test_does_not_descend_when_multiple_children(self):
        # Two sibling dirs and no top-level signal -> ambiguous, stay put.
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "a").mkdir()
            (root / "b").mkdir()
            self.assertEqual(scan._effective_root(root), root)

    def test_descends_into_sole_project_child_amid_noise(self):
        # A messy workspace: loose files + a non-project sibling (entry but no
        # .git/README) + exactly one real project (.git). Descend into the real one.
        with tempfile.TemporaryDirectory() as tmp:
            ws = pathlib.Path(tmp)
            (ws / "CLAUDE.md").write_text("workspace notes\n", encoding="utf-8")
            (ws / "loose.py").write_text("import sys\nx = sys.argv[1]\n", encoding="utf-8")
            sibling = ws / "sibling"          # entry but no .git/README -> not a project
            sibling.mkdir()
            (sibling / "run.py").write_text("import sys\nx = sys.argv[1]\n", encoding="utf-8")
            proj = ws / "real_project"        # .git -> independent project root
            (proj / "pkg").mkdir(parents=True)
            (proj / ".git").mkdir()
            (proj / "README.md").write_text("# real\n", encoding="utf-8")
            (proj / "pkg" / "main.py").write_text(
                "import sys\ncfg = sys.argv[1]\n", encoding="utf-8")
            self.assertEqual(scan._effective_root(ws), proj)
            sc = scan.scan_project(ws)
            self.assertEqual(sc["project_root"], str(proj))
            self.assertEqual((sc.get("primary_entry") or {}).get("path"), "pkg/main.py")

    def test_raises_on_multiple_project_children(self):
        # Two independent project roots (each .git) -> ambiguous workspace -> raise,
        # naming both candidates so the user can re-point --project-root.
        with tempfile.TemporaryDirectory() as tmp:
            ws = pathlib.Path(tmp)
            for name in ("proj_a", "proj_b"):
                d = ws / name
                d.mkdir()
                (d / ".git").mkdir()
                (d / f"{name}.py").write_text("import sys\nx = sys.argv[1]\n", encoding="utf-8")
            with self.assertRaises(scan.AmbiguousProjectRoot) as cm:
                scan._effective_root(ws)
            msg = str(cm.exception)
            self.assertIn("proj_a", msg)
            self.assertIn("proj_b", msg)


class ArgparseConstraintsTest(unittest.TestCase):
    SRC = (
        "import argparse\n"
        "p = argparse.ArgumentParser()\n"
        "p.add_argument('--eos', choices=['a','b'], required=True)\n"
        "p.add_argument('--n', type=int)\n"
        "g = p.add_mutually_exclusive_group()\n"
        "g.add_argument('--fast')\n"
        "g.add_argument('--slow')\n"
    )

    def test_required_choices_and_mutex(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / "cli.py"
            f.write_text(self.SRC, encoding="utf-8")
            params = {p["name"]: p for p in scan.extract_argparse_parameters(f)}
            self.assertEqual(params["eos"]["choices"], ["a", "b"])
            self.assertTrue(params["eos"]["required"])
            self.assertIsNone(params["n"].get("required"))
            self.assertEqual(params["fast"]["exclusive_group"],
                             params["slow"]["exclusive_group"])
            self.assertIsNotNone(params["fast"]["exclusive_group"])
            self.assertIsNone(params["eos"].get("exclusive_group"))


class ArgvRequiredTest(unittest.TestCase):
    def test_count_from_sys_argv_index_and_len_guard(self):
        text = ("import sys\n"
                "if len(sys.argv) == 6:\n"
                "    a = sys.argv[1]\n    b = sys.argv[2]\n    c = sys.argv[3]\n"
                "    d = sys.argv[4]\n    e = sys.argv[5]\n")
        # both signals agree on 5 positional args
        self.assertEqual(scan._argv_required_count(text), 5)

    def test_len_guard_exceeds_named_indices(self):
        # guard demands 4 positionals though only 2 sys.argv[i] are named -> 4
        text = "import sys\nif len(sys.argv) >= 5:\n    x = sys.argv[1]\n    y = sys.argv[2]\n"
        self.assertEqual(scan._argv_required_count(text), 4)

    def test_entry_signature_carries_argv_required(self):
        sig = scan._entry_signature("import sys\nif len(sys.argv)==6:\n    x=sys.argv[1]\n")
        self.assertEqual(sig["argv_required"], 5)


if __name__ == "__main__":
    unittest.main()
