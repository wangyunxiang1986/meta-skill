import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

LAUNCHER = pathlib.Path(__file__).resolve().parents[1] / "engine" / "templates" / "run_launcher.py"


class RunLauncherTest(unittest.TestCase):
    def test_t0_dry_run_resolves_command_without_executing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            (root / "pyvisc").mkdir(parents=True)
            (root / ".git").mkdir()
            (root / "pyvisc" / "base.info").write_text(
                "[General]\nout = ./x\n[ic]\ninitial = glauber\n", encoding="utf-8")
            profile = {
                "command_argv": ["python", "run.py", "{config}", "{cent}", "{gpu}", "0", "1"],
                "base_config": "pyvisc/base.info",
                "work_subdir": "pyvisc",
                "config_edits": {"initial": "trento"},
                "output_key": "out",
                "tier1_output": "hypersf.dat",
                "tier2_observable": "dNchdeta",
            }
            pf = pathlib.Path(tmp) / "run_profile.json"
            pf.write_text(json.dumps(profile), encoding="utf-8")
            work = pathlib.Path(tmp) / "work"
            proc = subprocess.run(
                [sys.executable, str(LAUNCHER), "--project-root", str(root),
                 "--work-dir", str(work), "--run-profile", str(pf),
                 "--cent", "0_5", "--gpu", "0", "--max-tier", "0"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            report = json.loads((work / "verification-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["tier_reached"], 0)
            edited = (work / "base.info").read_text(encoding="utf-8")
            self.assertIn("initial = trento", edited)
            self.assertIn(str(work), report["resolved_command"])

    def test_unfilled_angle_placeholder_blocks_at_t0(self):
        # C1: an engine-emitted <name> placeholder the pack could not fill must stop
        # the run at T0 with a clear blocker, not be passed literally to the program.
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            (root / "pyvisc").mkdir(parents=True)
            (root / ".git").mkdir()
            (root / "pyvisc" / "run.py").write_text("import sys\n", encoding="utf-8")
            profile = {
                # <coll_sys>/<event0>/<event1> unfilled -> must block before running
                "command_argv": ["python", "run.py", "<coll_sys>", "{cent}", "{gpu}",
                                 "<event0>", "<event1>"],
                "work_subdir": "pyvisc",
                "tier1_output": "hypersf.dat",
                "tier2_observable": "dNchdeta",
            }
            pf = pathlib.Path(tmp) / "run_profile.json"
            pf.write_text(json.dumps(profile), encoding="utf-8")
            work = pathlib.Path(tmp) / "work"
            proc = subprocess.run(
                [sys.executable, str(LAUNCHER), "--project-root", str(root),
                 "--work-dir", str(work), "--run-profile", str(pf),
                 "--cent", "0_5", "--gpu", "0", "--max-tier", "1"],  # tier 1 would run if not blocked
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            report = json.loads((work / "verification-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["tier_reached"], 0)                  # never reached T1
            blockers = " ".join(report["blockers"])
            self.assertIn("<coll_sys>", blockers)
            self.assertIn("<event0>", blockers)
            self.assertIn("placeholder", blockers)

    def test_t0_records_environment_check(self):
        # Engine-level test: synthetic, model-agnostic fixture (no CLVisc names).
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            (root / "src").mkdir(parents=True)
            (root / ".git").mkdir()
            (root / "src" / "base.cfg").write_text("[g]\nout = ./x\n", encoding="utf-8")
            profile = {
                "command_argv": ["python", "run.py", "{config}"],
                "base_config": "src/base.cfg",
                "work_subdir": "src",
                "tier1_output": "result.dat",
                "needs": ["build:nope", "opencl"],
            }
            pf = pathlib.Path(tmp) / "run_profile.json"
            pf.write_text(json.dumps(profile), encoding="utf-8")
            work = pathlib.Path(tmp) / "work"
            proc = subprocess.run(
                [sys.executable, str(LAUNCHER), "--project-root", str(root),
                 "--work-dir", str(work), "--run-profile", str(pf), "--max-tier", "0"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            report = json.loads((work / "verification-report.json").read_text(encoding="utf-8"))
            env = report["environment"]
            self.assertTrue(env["root_exists"])
            self.assertIn("python3", env["tools"])
            self.assertFalse(env["needs"]["build:nope"])   # missing build flagged at T0

    def test_t0_missing_base_config_is_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            root.mkdir()
            profile = {
                "command_argv": ["python", "run.py", "{config}"],
                "base_config": "missing/base.cfg",
                "work_subdir": ".",
                "tier1_output": "result.dat",
            }
            pf = pathlib.Path(tmp) / "run_profile.json"
            pf.write_text(json.dumps(profile), encoding="utf-8")
            work = pathlib.Path(tmp) / "work"
            proc = subprocess.run(
                [sys.executable, str(LAUNCHER), "--project-root", str(root),
                 "--work-dir", str(work), "--run-profile", str(pf), "--max-tier", "0"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            report = json.loads((work / "verification-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["tier_reached"], 0)
            self.assertTrue(any("base_config missing" in b for b in report["blockers"]))
            self.assertFalse((work / "base.cfg").exists())

    def test_descends_wrapper_dir_for_project_root(self):
        # Given an outer wrapper dir, the launcher resolves to the inner project
        # (same single-wrapper descent the scanner uses), so relative paths and
        # build needs resolve correctly. Engine-level, model-agnostic.
        with tempfile.TemporaryDirectory() as tmp:
            wrapper = pathlib.Path(tmp) / "wrapper"
            inner = wrapper / "Project"
            (inner / "src").mkdir(parents=True)
            (inner / "src" / "base.cfg").write_text("[g]\nout = ./x\n", encoding="utf-8")
            (inner / "lib" / "build").mkdir(parents=True)
            profile = {
                "command_argv": ["python", "run.py", "{config}"],
                "base_config": "src/base.cfg",
                "work_subdir": "src",
                "tier1_output": "result.dat",
                "needs": ["build:lib"],
            }
            pf = pathlib.Path(tmp) / "run_profile.json"
            pf.write_text(json.dumps(profile), encoding="utf-8")
            work = pathlib.Path(tmp) / "work"
            proc = subprocess.run(
                [sys.executable, str(LAUNCHER), "--project-root", str(wrapper),
                 "--work-dir", str(work), "--run-profile", str(pf), "--max-tier", "0"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            report = json.loads((work / "verification-report.json").read_text(encoding="utf-8"))
            # descended into Project -> build:lib resolves, base.cfg was found+edited
            self.assertTrue(report["environment"]["needs"]["build:lib"])
            self.assertIn("[g]", (work / "base.cfg").read_text(encoding="utf-8"))

    def test_descends_into_sole_project_child_amid_noise(self):
        # Messy workspace: a loose file + a non-project sibling (entry, no .git/
        # README) + exactly one real project (.git + README). Descend into the
        # project so relative paths / build needs resolve. Model-agnostic.
        with tempfile.TemporaryDirectory() as tmp:
            ws = pathlib.Path(tmp) / "ws"
            ws.mkdir()
            (ws / "CLAUDE.md").write_text("workspace notes\n", encoding="utf-8")
            sib = ws / "sibling"
            sib.mkdir()
            (sib / "run.py").write_text("import sys\nx = sys.argv[1]\n", encoding="utf-8")
            proj = ws / "real_project"
            (proj / "src").mkdir(parents=True)
            (proj / ".git").mkdir()
            (proj / "README.md").write_text("# real\n", encoding="utf-8")
            (proj / "src" / "base.cfg").write_text("[g]\nout = ./x\n", encoding="utf-8")
            (proj / "lib" / "build").mkdir(parents=True)
            profile = {
                "command_argv": ["python", "run.py", "{config}"],
                "base_config": "src/base.cfg",
                "work_subdir": "src",
                "tier1_output": "result.dat",
                "needs": ["build:lib"],
            }
            pf = pathlib.Path(tmp) / "run_profile.json"
            pf.write_text(json.dumps(profile), encoding="utf-8")
            work = pathlib.Path(tmp) / "work"
            proc = subprocess.run(
                [sys.executable, str(LAUNCHER), "--project-root", str(ws),
                 "--work-dir", str(work), "--run-profile", str(pf), "--max-tier", "0"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            report = json.loads((work / "verification-report.json").read_text(encoding="utf-8"))
            self.assertTrue(report["environment"]["needs"]["build:lib"])
            self.assertIn("[g]", (work / "base.cfg").read_text(encoding="utf-8"))

    def test_refuses_multi_project_workspace(self):
        # Two independent project roots -> ambiguous workspace -> clean stderr
        # message + exit code 2 (mirrors the scanner's AmbiguousProjectRoot).
        with tempfile.TemporaryDirectory() as tmp:
            ws = pathlib.Path(tmp) / "ws"
            ws.mkdir()
            for name in ("proj_a", "proj_b"):
                d = ws / name
                d.mkdir()
                (d / ".git").mkdir()
                (d / "README.md").write_text("# x\n", encoding="utf-8")
            profile = {"command_argv": ["python", "run.py", "{config}"],
                       "base_config": "base.cfg"}
            pf = pathlib.Path(tmp) / "run_profile.json"
            pf.write_text(json.dumps(profile), encoding="utf-8")
            work = pathlib.Path(tmp) / "work"
            proc = subprocess.run(
                [sys.executable, str(LAUNCHER), "--project-root", str(ws),
                 "--work-dir", str(work), "--run-profile", str(pf), "--max-tier", "0"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn("multi-project workspace", proc.stderr)
            self.assertIn("proj_a", proc.stderr)
            self.assertIn("proj_b", proc.stderr)


    def test_build_prepare_run_in_work_with_params(self):
        # Generic build -> prepare -> run sequencer: build runs in the project
        # root, prepare+run in an isolated work dir, with {placeholder} substitution
        # from profile params. Model-agnostic (synthetic, no model names).
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            (root / "src").mkdir(parents=True)
            (root / ".git").mkdir()
            profile = {
                "build": ["python3 -c \"open('built.marker','w').write('ok')\""],
                "prepare": ["python3 -c \"open('prepared_{jobid}.txt','w').write('p')\""],
                "run_in": "work",
                "params": {"jobid": "7"},
                "command_argv": ["python3", "-c",
                                 "open('out.dat','w').write('1 2 3')"],
                "tier1_output": "out.dat",
            }
            pf = pathlib.Path(tmp) / "run_profile.json"
            pf.write_text(json.dumps(profile), encoding="utf-8")
            work = pathlib.Path(tmp) / "work"
            proc = subprocess.run(
                [sys.executable, str(LAUNCHER), "--project-root", str(root),
                 "--work-dir", str(work), "--run-profile", str(pf), "--max-tier", "1"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            report = json.loads((work / "verification-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["tier_reached"], 1, report["blockers"])
            self.assertTrue((root / "built.marker").exists())          # build ran in root
            self.assertTrue((work / "run" / "prepared_7.txt").exists())  # prepare subst {jobid}
            self.assertTrue(report["tier1_output"].endswith("out.dat"))

    def test_missing_required_input_is_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            (root / ".git").mkdir(parents=True)
            profile = {
                "inputs": {"data_root": None},
                "run_in": "work",
                "prepare": ["python3 -c \"open('x','w').write('{data_root}')\""],
                "command_argv": ["python3", "-c", "pass"],
                "tier1_output": "out.dat",
            }
            pf = pathlib.Path(tmp) / "run_profile.json"
            pf.write_text(json.dumps(profile), encoding="utf-8")
            work = pathlib.Path(tmp) / "work"
            proc = subprocess.run(
                [sys.executable, str(LAUNCHER), "--project-root", str(root),
                 "--work-dir", str(work), "--run-profile", str(pf), "--max-tier", "1"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            report = json.loads((work / "verification-report.json").read_text(encoding="utf-8"))
            self.assertTrue(any("data_root" in b for b in report["blockers"]))

    def test_provided_input_substituted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            (root / ".git").mkdir(parents=True)
            profile = {
                "inputs": {"data_root": None},
                "run_in": "work",
                "prepare": ["python3 -c \"open('seen.txt','w').write('{data_root}')\""],
                "command_argv": ["python3", "-c", "open('out.dat','w').write('ok')"],
                "tier1_output": "out.dat",
            }
            pf = pathlib.Path(tmp) / "run_profile.json"
            pf.write_text(json.dumps(profile), encoding="utf-8")
            work = pathlib.Path(tmp) / "work"
            proc = subprocess.run(
                [sys.executable, str(LAUNCHER), "--project-root", str(root),
                 "--work-dir", str(work), "--run-profile", str(pf), "--max-tier", "1",
                 "--input", "data_root=/tmp/my_data"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            report = json.loads((work / "verification-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["tier_reached"], 1, report["blockers"])
            self.assertEqual((work / "run" / "seen.txt").read_text(encoding="utf-8"),
                             "/tmp/my_data")

    def test_failed_run_not_counted_as_tier1(self):
        # Finding 1: a non-zero run exit must be a hard stop. A pre-existing
        # tier1_output (here written by prepare) must NOT make T1 "reached" --
        # otherwise a failed run gets logged as known-good in verified-runs.
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            (root / ".git").mkdir(parents=True)
            profile = {
                "run_in": "work",
                "prepare": ["python3 -c \"open('out.dat','w').write('stale')\""],
                "command_argv": ["python3", "-c", "import sys; sys.exit(3)"],
                "tier1_output": "out.dat",
            }
            pf = pathlib.Path(tmp) / "run_profile.json"
            pf.write_text(json.dumps(profile), encoding="utf-8")
            work = pathlib.Path(tmp) / "work"
            proc = subprocess.run(
                [sys.executable, str(LAUNCHER), "--project-root", str(root),
                 "--work-dir", str(work), "--run-profile", str(pf), "--max-tier", "1"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            report = json.loads((work / "verification-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["tier_reached"], 0, report)
            self.assertTrue(any("exited 3" in b for b in report["blockers"]), report["blockers"])

    def test_stale_output_not_counted_as_fresh_tier1(self):
        # Finding 2: run exits 0 but produces nothing; a stale tier1_output left
        # in the run cwd by a previous run must not be mistaken for this run's
        # output (freshness by mtime).
        import os
        import time
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            (root / ".git").mkdir(parents=True)
            work = pathlib.Path(tmp) / "work"
            runcwd = work / "run"
            runcwd.mkdir(parents=True)
            stale = runcwd / "out.dat"
            stale.write_text("stale", encoding="utf-8")
            old = time.time() - 100
            os.utime(stale, (old, old))
            profile = {
                "run_in": "work",
                "command_argv": ["python3", "-c", "pass"],   # exit 0, writes nothing
                "tier1_output": "out.dat",
            }
            pf = pathlib.Path(tmp) / "run_profile.json"
            pf.write_text(json.dumps(profile), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(LAUNCHER), "--project-root", str(root),
                 "--work-dir", str(work), "--run-profile", str(pf), "--max-tier", "1"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            report = json.loads((work / "verification-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["tier_reached"], 0, report)
            self.assertTrue(any("missing" in b for b in report["blockers"]), report["blockers"])

    def test_t2_extractor_error_not_counted_as_success(self):
        # A2: an extractor that gracefully returns {"error": ...} (e.g. the file
        # exists but has no usable rows) must NOT count as T2 reached.
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            (root / ".git").mkdir(parents=True)
            ext = pathlib.Path(tmp) / "extractors.py"
            ext.write_text(
                "def extract(observable, run_dir, out_dir):\n"
                "    return {'observable': observable, 'error': 'no rows parsed'}\n",
                encoding="utf-8")
            profile = {
                "run_in": "work",
                "command_argv": ["python3", "-c", "open('out.dat','w').write('1 2 3')"],
                "tier1_output": "out.dat",
                "tier2_observable": "dNdpT",
            }
            pf = pathlib.Path(tmp) / "run_profile.json"
            pf.write_text(json.dumps(profile), encoding="utf-8")
            work = pathlib.Path(tmp) / "work"
            proc = subprocess.run(
                [sys.executable, str(LAUNCHER), "--project-root", str(root),
                 "--work-dir", str(work), "--run-profile", str(pf),
                 "--extractors", str(ext), "--max-tier", "2"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            report = json.loads((work / "verification-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["tier_reached"], 1, report)        # T1, not T2
            self.assertTrue(any("no rows parsed" in b or "observable" in b
                                for b in report["blockers"]), report["blockers"])

    def test_t2_successful_extractor_reaches_tier2(self):
        # Regression: a genuine extractor (dict, no 'error') still reaches T2.
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            (root / ".git").mkdir(parents=True)
            ext = pathlib.Path(tmp) / "extractors.py"
            ext.write_text(
                "import os\n"
                "def extract(observable, run_dir, out_dir):\n"
                "    os.makedirs(out_dir, exist_ok=True)\n"
                "    p = os.path.join(out_dir, 'plot.png'); open(p, 'w').write('x')\n"
                "    return {'observable': observable, 'values': {'n': 3}, 'plot': p}\n",
                encoding="utf-8")
            profile = {
                "run_in": "work",
                "command_argv": ["python3", "-c", "open('out.dat','w').write('1 2 3')"],
                "tier1_output": "out.dat",
                "tier2_observable": "dNdpT",
            }
            pf = pathlib.Path(tmp) / "run_profile.json"
            pf.write_text(json.dumps(profile), encoding="utf-8")
            work = pathlib.Path(tmp) / "work"
            proc = subprocess.run(
                [sys.executable, str(LAUNCHER), "--project-root", str(root),
                 "--work-dir", str(work), "--run-profile", str(pf),
                 "--extractors", str(ext), "--max-tier", "2"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            report = json.loads((work / "verification-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["tier_reached"], 2, report)
            self.assertEqual(report["blockers"], [])

    def test_apply_edits_value_with_escape_is_literal(self):
        # B2: a config value containing a backslash (e.g. a Windows path, or
        # here \t) must be written literally, not interpreted as a regex
        # replacement escape.
        import importlib.util
        spec = importlib.util.spec_from_file_location("gen_launcher", LAUNCHER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out = mod._apply_edits("path = old\nkeep = 1\n", {"path": "a\\tb"}, None, None)
        self.assertIn("path = a\\tb", out)     # literal backslash-t, not a TAB
        self.assertIn("keep = 1", out)

    def test_write_verified_run_records_into_skill(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("gen_launcher", LAUNCHER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as tmp:
            skill = pathlib.Path(tmp) / "generated-skill"
            (skill / "references").mkdir(parents=True)
            (skill / "scripts").mkdir(parents=True)
            rp = skill / "scripts" / "run_profile.json"
            rp.write_text("{}", encoding="utf-8")
            mod._write_verified_run(
                {"tier_reached": 1, "resolved_command": "python CLVisc.py cfg 0_5 0 0 1"},
                str(rp))
            mod._write_verified_run(
                {"tier_reached": 2, "resolved_command": "python run.py cfg"},
                str(rp))
            vr = (skill / "references" / "verified-runs.md").read_text(encoding="utf-8")
            self.assertIn("T1", vr)
            self.assertIn("T2", vr)
            self.assertIn("python CLVisc.py cfg 0_5 0 0 1", vr)
            self.assertIn("python run.py cfg", vr)
            # tier 0 -> nothing written
            (skill / "references" / "verified-runs.md").unlink()
            mod._write_verified_run({"tier_reached": 0, "resolved_command": "x"}, str(rp))
            self.assertFalse((skill / "references" / "verified-runs.md").exists())

    def test_write_blocked_run_appends_into_skill(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("gen_launcher", LAUNCHER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as tmp:
            skill = pathlib.Path(tmp) / "generated-skill"
            (skill / "references").mkdir(parents=True)
            (skill / "scripts").mkdir(parents=True)
            rp = skill / "scripts" / "run_profile.json"
            rp.write_text("{}", encoding="utf-8")
            mod._write_blocked_run(
                {"tier_reached": 0, "resolved_command": "python x", "blockers": ["missing cfg"]},
                str(rp))
            mod._write_blocked_run(
                {"tier_reached": 1, "resolved_command": "python y", "blockers": ["missing output"]},
                str(rp))
            br = (skill / "references" / "blocked-runs.md").read_text(encoding="utf-8")
            self.assertIn("missing cfg", br)
            self.assertIn("missing output", br)
            self.assertIn("python x", br)
            self.assertIn("python y", br)


    def test_input_default_resolves_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            (root / "data").mkdir(parents=True)
            (root / ".git").mkdir()             # anchor: prevents _effective_root from descending
            (root / "data" / "x.dat").write_text("x", encoding="utf-8")
            profile = {"command_argv": ["./run", "{oscar_file}", "out.dat"],
                       "inputs": {"oscar_file": "<PROJECT_ROOT>/data/x.dat"}}
            pf = pathlib.Path(tmp) / "run_profile.json"
            pf.write_text(json.dumps(profile), encoding="utf-8")
            work = pathlib.Path(tmp) / "work"
            proc = subprocess.run(
                [sys.executable, str(LAUNCHER), "--project-root", str(root),
                 "--work-dir", str(work), "--run-profile", str(pf), "--max-tier", "0"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            report = json.loads((work / "verification-report.json").read_text(encoding="utf-8"))
            self.assertIn(str(root / "data" / "x.dat"), report["resolved_command"])
            self.assertNotIn("<PROJECT_ROOT>", report["resolved_command"])


if __name__ == "__main__":
    unittest.main()
