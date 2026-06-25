import pathlib
import subprocess
import sys
import tempfile
import unittest
from engine import generate

ENGINE_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _scan(**kw):
    base = {"readme_path": None, "primary_entry": None, "readme_commands": [],
            "parameters": [], "output_files": [], "entrypoints": [],
            "build_targets": [], "build_files": [], "dependencies": [],
            "project_root": "/tmp/Demo"}
    base.update(kw)
    return base


class ReadmeStatusTest(unittest.TestCase):
    def test_missing_when_no_readme(self):
        self.assertEqual(generate.readme_status(_scan(readme_path=None)), "missing")

    def test_problematic_when_readme_arg_count_stale(self):
        scan = _scan(
            readme_path="README.md",
            primary_entry={"path": "run.py", "argv_names": ["a", "b", "c"],
                           "argv_required": 3},
            readme_commands=["python run.py X"])   # README shows 1 positional, code needs 3
        self.assertEqual(generate.readme_status(scan), "problematic")

    def test_ok_when_readme_present_and_consistent(self):
        scan = _scan(
            readme_path="README.md",
            primary_entry={"path": "run.py", "argv_names": ["a"], "argv_required": 1},
            readme_commands=["python run.py X"])
        self.assertEqual(generate.readme_status(scan), "ok")


class ReadmeInstallFilterTest(unittest.TestCase):
    def test_prose_dependency_lines_are_filtered_out(self):
        # scan["dependencies"] can pick up README prose (markdown headers, numbered
        # install steps, sentences). The Installation section must keep short
        # tool-name-ish deps and drop the prose. (Real CLVisc regression.)
        scan = _scan(dependencies=[
            "= CLVisc: a (3+1)D viscous hydrodynamic program parallelized on GPU =",
            "1. Install OpenCL",
            "(2) For Linux using Nvidia GPU, install CUDA -- Shipped with OpenCL.",
            "`conda install -c conda-forge pyopencl`",
            "export PATH=[gsl_path]/bin:$PATH",
            "cmake",
            "gsl",
        ])
        lines = generate._readme_install(scan, None)
        text = "\n".join(lines)
        # short tool names kept
        self.assertIn("- cmake", text)
        self.assertIn("- gsl", text)
        # prose dropped
        self.assertNotIn("CLVisc: a (3+1)D", text)
        self.assertNotIn("1. Install OpenCL", text)
        self.assertNotIn("For Linux using Nvidia GPU", text)
        self.assertNotIn("export PATH", text)

    def test_command_fragments_dropped_and_deduped(self):
        # "cmake .." style build-command fragments (path-like, repeated) are noise.
        scan = _scan(dependencies=["cmake ..", "cmake ..", "gsl", "gsl", "src/foo"])
        lines = generate._readme_install(scan, None)
        text = "\n".join(lines)
        self.assertNotIn("cmake ..", text)        # path-like fragment dropped
        self.assertNotIn("src/foo", text)         # path dropped
        self.assertEqual(text.count("- gsl"), 1)  # deduped

    def test_pack_run_profile_build_step_surfaces(self):
        # When the structural scanner detects no build file but the pack's run
        # profile declares a build step, the Installation section must still show
        # it -- otherwise the generated README documents a code that won't run.
        scan = _scan(build_files=[], build_targets=[])
        knowledge = {"run_profiles": {"minimal": {"build": ["make"]}}}
        text = "\n".join(generate._readme_install(scan, knowledge))
        self.assertIn("make", text)

    def test_pack_build_placeholder_steps_are_not_dumped(self):
        # Launcher-internal scratch-build steps (with {work}/{root} placeholders
        # or absolute paths) are not user install instructions; drop them.
        scan = _scan(build_files=[], build_targets=[])
        knowledge = {"run_profiles": {"minimal": {"build": [
            "mkdir -p {work}/build", "cp {root}/*.cpp {work}/build/",
            "make -C {work}/build"]}}}
        text = "\n".join(generate._readme_install(scan, knowledge))
        self.assertNotIn("{work}", text)
        self.assertNotIn("{root}", text)

    def test_no_dependencies_block_when_all_prose(self):
        scan = _scan(dependencies=["1. Install OpenCL", "2. Download Anaconda"],
                     build_files=["Makefile"])
        text = "\n".join(generate._readme_install(scan, None))
        self.assertNotIn("Dependencies:", text)   # nothing real survived the filter
        self.assertIn("make", text)               # build still shown


class RenderReadmeTest(unittest.TestCase):
    def _pack(self):
        return {"name": "demo", "knowledge": {
            "description": "Demo transport code.",
            "run_profiles": {"minimal": {
                "command": ["./demo", "0"], "build": ["make"],
                "tier1_output": "out.dat"}},
            "demos": [{"title": "smoke", "intent": "minimal run",
                       "args": {"cent": "0_5"}}]}}

    def test_has_four_sections_and_derived_content(self):
        scan = _scan(project_root="/tmp/Demo", build_files=["Makefile"],
                     primary_entry={"path": "main.cpp", "argv_names": ["jobid"],
                                    "argv_required": 1, "run_prefix": ["./demo"]})
        md = generate.render_readme(scan, self._pack())
        for header in ("# Demo", "## Description", "## Installation",
                       "## Usage", "## Example"):
            self.assertIn(header, md)
        self.assertIn("Demo transport code.", md)        # description from pack
        self.assertIn("make", md)                         # install
        self.assertIn("./demo 0", md)                     # usage = derived command
        self.assertIn("minimal run", md)                  # example intent from demos
        self.assertIn("generated by project-explorer", md)  # provenance marker

    def test_problematic_adds_notes_section(self):
        scan = _scan(
            readme_path="README.md",
            primary_entry={"path": "run.py", "argv_names": ["a", "b", "c"],
                           "argv_required": 3},
            readme_commands=["python run.py X"])
        md = generate.render_readme(scan, None)
        self.assertIn("## Notes on the existing README", md)
        self.assertIn("requires 3", md)

    def test_no_notes_when_missing(self):
        scan = _scan(readme_path=None,
                     primary_entry={"path": "run.py", "argv_names": ["a"],
                                    "argv_required": 1})
        md = generate.render_readme(scan, None)
        self.assertNotIn("Notes on the existing README", md)


class GenerateWritesReadmeTest(unittest.TestCase):
    def _scan_missing(self, root):
        return {"readme_path": None, "primary_entry":
                {"path": "main.cpp", "argv_names": ["jobid"], "argv_required": 1,
                 "run_prefix": ["./demo"]},
                "readme_commands": [], "parameters": [], "output_files": [],
                "entrypoints": [], "build_targets": [], "build_files": ["Makefile"],
                "dependencies": [], "git": {}, "directories": [], "file_counts": {},
                "project_root": str(root)}

    def test_generate_writes_readme_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "Demo"
            root.mkdir()
            out = pathlib.Path(tmp) / "skill"
            report = generate.generate(self._scan_missing(root), None, out)
            readme = out / "references" / "generated-README.md"
            self.assertTrue(readme.exists())
            self.assertIn("## Usage", readme.read_text(encoding="utf-8"))
            self.assertEqual(report["readme_status"], "missing")

    def test_generate_removes_stale_readme_when_now_ok(self):
        # A previously-generated README must be cleaned when a later scan is ok
        # (clean_generated_files), not left behind as misleading documentation.
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "Demo"
            root.mkdir()
            out = pathlib.Path(tmp) / "skill"
            stale = out / "references" / "generated-README.md"
            stale.parent.mkdir(parents=True)
            stale.write_text("OLD GENERATED README", encoding="utf-8")
            scan = self._scan_missing(root)
            scan["readme_path"] = "README.md"        # now present + consistent -> ok
            generate.generate(scan, None, out)
            self.assertFalse(stale.exists())

    def test_generate_skips_readme_when_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "Demo"
            root.mkdir()
            scan = self._scan_missing(root)
            scan["readme_path"] = "README.md"        # present + consistent -> ok
            out = pathlib.Path(tmp) / "skill"
            report = generate.generate(scan, None, out)
            self.assertFalse((out / "references" / "generated-README.md").exists())
            self.assertEqual(report["readme_status"], "ok")


class ReadmeSourceTargetTest(unittest.TestCase):
    def test_missing_and_absent_writes_readme_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(generate.readme_source_target("missing", tmp),
                             pathlib.Path(tmp) / "README.md")

    def test_missing_but_readme_exists_writes_generated(self):
        # The defensive branch: status says missing yet a README.md is present
        # (e.g. it appeared after the scan). Must NOT clobber it.
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / "README.md").write_text("MINE", encoding="utf-8")
            self.assertEqual(generate.readme_source_target("missing", tmp),
                             pathlib.Path(tmp) / "README.generated.md")

    def test_problematic_writes_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(generate.readme_source_target("problematic", tmp),
                             pathlib.Path(tmp) / "README.generated.md")


class IntoSourceCliTest(unittest.TestCase):
    def _run(self, root, out, extra):
        return subprocess.run(
            [sys.executable, "-m", "engine.generate",
             "--project-root", str(root), "--out-dir", str(out),
             "--packs-dir", str(ENGINE_ROOT / "packs")] + extra,
            cwd=str(ENGINE_ROOT), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def test_into_source_writes_readme_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            root.mkdir()
            (root / "cli.py").write_text("import sys\nx = sys.argv[1]\n", encoding="utf-8")
            out = pathlib.Path(tmp) / "skill"
            proc = self._run(root, out, ["--into-source"])
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertTrue((root / "README.md").exists())

    def test_default_does_not_touch_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            root.mkdir()
            (root / "cli.py").write_text("import sys\nx = sys.argv[1]\n", encoding="utf-8")
            out = pathlib.Path(tmp) / "skill"
            proc = self._run(root, out, [])           # no --into-source
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertFalse((root / "README.md").exists())
            self.assertTrue((out / "references" / "generated-README.md").exists())

    def test_into_source_never_overwrites_existing_readme(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            root.mkdir()
            # stale README: documents 0 positionals, code needs 1 -> problematic.
            # The command line must start with `python ...` so the scanner's README
            # command parser picks it up (a `run: ...` prefix is not recognized).
            (root / "cli.py").write_text("import sys\nx = sys.argv[1]\n", encoding="utf-8")
            (root / "README.md").write_text("python cli.py\nMINE\n", encoding="utf-8")
            out = pathlib.Path(tmp) / "skill"
            proc = self._run(root, out, ["--into-source"])
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn("MINE", (root / "README.md").read_text(encoding="utf-8"))
            self.assertTrue((root / "README.generated.md").exists())


if __name__ == "__main__":
    unittest.main()
