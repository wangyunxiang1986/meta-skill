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


class VendoredExclusionTest(unittest.TestCase):
    """Vendored / third-party trees must not pollute the scan (B1). Their params,
    build targets, entries and config files are not this project's run surface."""

    def test_vendored_trees_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            # the project's own surface
            (root / "src").mkdir()
            (root / "src" / "main.cpp").write_text("int main(int argc,char**argv){}", encoding="utf-8")
            (root / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.0)\n", encoding="utf-8")
            (root / "README.md").write_text("demo\n", encoding="utf-8")
            # vendored noise that must be ignored
            for vend in ("3rdparty", "external", "third_party", "subprojects", "_deps"):
                d = root / vend / "libfoo"
                d.mkdir(parents=True)
                (d / "CMakeLists.txt").write_text("project(foo)\n", encoding="utf-8")
                (d / "cli.py").write_text(
                    "import argparse;p=argparse.ArgumentParser();p.add_argument('--vend');p.parse_args()",
                    encoding="utf-8")
                (d / ".travis.yml").write_text("language: cpp\n", encoding="utf-8")

            files = scan.scan_files(root)
            joined = " ".join(files["build_files"] + files["config_files"] + files["source"])
            for vend in ("3rdparty", "external", "third_party", "subprojects", "_deps"):
                self.assertNotIn(vend, joined, "%s leaked into scan" % vend)
            # the project's own CMakeLists is still a build target; vendored ones are not
            targets = scan.build_targets(root)
            self.assertIn(".", targets)                       # root-level build kept
            self.assertFalse(any("3rdparty" in t or "external" in t for t in targets))
            # the vendored argparse param must not appear
            sc = scan.scan_project(root)
            self.assertNotIn("vend", [p.get("name") for p in sc.get("parameters", [])])


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


class ShellEntryTest(unittest.TestCase):
    def test_detect_shell_entry_names_and_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "afterburner").write_text(
                "#!/bin/bash\ninputfile=$1\noutputfile=$2\n./osc2u < $inputfile\n",
                encoding="utf-8")
            entries = scan.detect_shell_entrypoints(root)
            self.assertEqual(len(entries), 1)
            e = entries[0]
            self.assertEqual(e["lang"], "shell")
            self.assertEqual(e["argv_names"], ["inputfile", "outputfile"])
            self.assertEqual(e["argv_required"], 2)
            self.assertEqual(e["run_prefix"], ["./afterburner"])

    def test_scan_project_falls_back_to_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "model.f").write_text("      program x\n      end\n", encoding="utf-8")
            (root / "run.sh").write_text("#!/bin/bash\nin=$1\nout=$2\n", encoding="utf-8")
            sc = scan.scan_project(root)
            self.assertEqual((sc.get("primary_entry") or {}).get("path"), "run.sh")
            self.assertEqual(sc["primary_entry"]["argv_names"], ["in", "out"])


if __name__ == "__main__":
    unittest.main()
