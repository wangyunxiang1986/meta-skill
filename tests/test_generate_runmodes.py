import unittest

from engine import generate


class RunModesTest(unittest.TestCase):
    def test_runmodes_from_profile_derives_command_from_scan(self):
        knowledge = {"run_profiles": {"minimal": {
            "driver": {"arg_map": {"config": ["cfg"]}, "arg_defaults": {"default": "0"}},
            "tier1_output": "result.dat", "tier2_observable": "y"}}}
        entry = {"path": "run.py", "cli_style": "argv", "argv_names": ["cfg"]}
        scan = {"entrypoints": [entry], "primary_entry": entry, "build_targets": []}
        md = generate.render_run_modes(scan, knowledge)
        self.assertIn("python run.py", md)   # entry name comes from scan
        self.assertIn("{config}", md)         # slot mapped via arg_map
        self.assertIn("result.dat", md)

    def test_resolve_command_argv_fills_slots_and_defaults(self):
        entry = {"path": "pyvisc/CLVisc.py", "cli_style": "argv",
                 "argv_names": ["fconfig", "cent", "gpu_id", "start_id", "end_id"]}
        driver = {"arg_map": {"config": ["fconfig", "config"], "cent": ["cent"], "gpu": ["gpu"]},
                  "arg_defaults": {"start_id": "0", "end_id": "1", "default": "0"}}
        argv = generate.resolve_command_argv({"primary_entry": entry}, driver,
                                             work_subdir="pyvisc")
        self.assertEqual(argv, ["python", "CLVisc.py", "{config}", "{cent}", "{gpu}", "0", "1"])

    def test_preserves_entry_subdir_when_workdir_is_root(self):
        entry = {"path": "scripts/driver.py", "cli_style": "argv",
                 "argv_names": ["fconfig"], "argv_required": 1}
        scan = {"primary_entry": entry, "readme_commands": []}
        argv = generate.resolve_command_argv(scan, {"arg_map": {"config": ["fconfig"]}},
                                             work_subdir=".")
        self.assertEqual(argv, ["python", "scripts/driver.py", "{config}"])

    def test_uses_basename_when_workdir_is_entry_parent(self):
        entry = {"path": "scripts/driver.py", "cli_style": "argv",
                 "argv_names": ["fconfig"], "argv_required": 1}
        scan = {"primary_entry": entry, "readme_commands": []}
        argv = generate.resolve_command_argv(scan, {"arg_map": {"config": ["fconfig"]}},
                                             work_subdir="scripts")
        self.assertEqual(argv, ["python", "driver.py", "{config}"])

    def test_resolve_prefers_readme_command_over_code_args(self):
        entry = {"path": "pyvisc/ebe_trento.py", "cli_style": "argv", "argv_names": ["x"]}
        scan = {"primary_entry": entry,
                "readme_commands": ["python ebe_trento.py collision_sys centrality gpu_id num"]}
        driver = {"arg_map": {"cent": ["cent"], "gpu": ["gpu"]}, "arg_defaults": {"default": "0"}}
        argv = generate.resolve_command_argv(scan, driver, work_subdir="pyvisc")
        # uses README arg names (centrality->cent, gpu_id->gpu), not code argv_names ["x"]
        self.assertEqual(argv, ["python", "ebe_trento.py", "0", "{cent}", "{gpu}", "0"])

    def test_resolve_pairs_template_and_example_from_readme(self):
        entry = {"path": "pyvisc/ebe_trento.py", "cli_style": "argv", "argv_names": ["x"]}
        scan = {"primary_entry": entry, "readme_commands": [
            "python ebe_trento.py collision_sys centrality gpu_id num_of_events",
            "python ebe_trento.py auau200 0_5 0 100"]}
        driver = {"arg_map": {"cent": ["cent"], "gpu": ["gpu"]}, "arg_defaults": {"default": "0"}}
        argv = generate.resolve_command_argv(scan, driver, work_subdir="pyvisc")
        # non-slot args (collision_sys, num) take the README EXAMPLE's real values
        self.assertEqual(argv, ["python", "ebe_trento.py", "auau200", "{cent}", "{gpu}", "100"])

    def test_defers_to_code_when_readme_undercounts_args(self):
        # README documents 4 args but the code requires 5 -> README is stale,
        # reconstruct from the code. Non-slot args with no pack default become
        # <name> placeholders (their values are the user's to fill).
        entry = {"path": "pyvisc/ebe_trento.py", "cli_style": "argv",
                 "argv_names": ["coll_sys", "cent", "gpu_id", "event0", "event1"],
                 "argv_required": 5}
        scan = {"primary_entry": entry, "readme_commands": [
            "python ebe_trento.py collision_sys centrality gpu_id num_of_events",
            "python ebe_trento.py auau200 0_5 0 100"]}
        # no catch-all default -> non-slot args become <name> placeholders
        driver = {"arg_map": {"config": ["fconfig", "config"], "cent": ["cent"], "gpu": ["gpu"]},
                  "arg_defaults": {}}
        argv = generate.resolve_command_argv(scan, driver, work_subdir="pyvisc")
        self.assertEqual(argv, ["python", "ebe_trento.py",
                                "<coll_sys>", "{cent}", "{gpu}", "<event0>", "<event1>"])

    def test_readme_arg_mismatch_reports_counts(self):
        entry = {"path": "pyvisc/ebe_trento.py", "argv_names": ["a", "b", "c", "d", "e"],
                 "argv_required": 5}
        scan = {"primary_entry": entry,
                "readme_commands": ["python ebe_trento.py s c g n"]}
        self.assertEqual(generate.readme_arg_mismatch(scan),
                         {"readme_argc": 4, "code_argc": 5})

    def test_no_mismatch_when_readme_has_enough_args(self):
        entry = {"path": "pyvisc/ebe_trento.py", "argv_names": ["x"], "argv_required": 1}
        scan = {"primary_entry": entry,
                "readme_commands": ["python ebe_trento.py s c g n"]}
        self.assertIsNone(generate.readme_arg_mismatch(scan))

    def test_runmodes_generic_no_pack(self):
        scan = {"entrypoints": [{"path": "cli.py", "cli_style": "argv",
                                 "argv_names": ["cfg", "n"]}], "build_targets": []}
        md = generate.render_run_modes(scan, None)
        self.assertIn("python cli.py", md)
        self.assertIn("<cfg>", md)

    def test_run_modes_redact_readme_commands(self):
        scan = {"entrypoints": [], "readme_commands": ["python /tmp/proj/scripts/run.py --x"],
                "build_targets": [], "project_root": "/tmp/proj"}
        md = generate.render_run_modes(scan, None, project_root="/tmp/proj")
        self.assertNotIn("/tmp/proj", md)
        self.assertIn("<PROJECT_ROOT>/scripts/run.py", md)


if __name__ == "__main__":
    unittest.main()
