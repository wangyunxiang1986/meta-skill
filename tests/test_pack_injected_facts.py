import unittest

from engine import generate


def _scan(**kw):
    base = {"parameters": [], "output_files": [], "entrypoints": [],
            "readme_commands": [], "primary_entry": None}
    base.update(kw)
    return base


class PackInjectedParametersTest(unittest.TestCase):
    def test_pack_parameters_render_when_scan_empty(self):
        scan = _scan()
        knowledge = {"pack_parameters": [
            {"name": "alphas", "default": "0.27", "meaning": "strong coupling",
             "range": [0.1, 0.5], "source": "LBTinput.txt"},
        ]}
        md = generate.render_parameters(scan, knowledge)
        self.assertIn("alphas", md)
        self.assertIn("strong coupling", md)
        self.assertIn("LBTinput.txt", md)
        self.assertIn("0.1..0.5", md)

    def test_scan_param_not_duplicated_by_pack(self):
        scan = _scan(parameters=[{"name": "alphas", "type": "float", "default": "0.3"}])
        knowledge = {"param_meaning": {"alphas": "coupling"},
                     "pack_parameters": [{"name": "alphas", "meaning": "coupling"}]}
        md = generate.render_parameters(scan, knowledge)
        self.assertEqual(md.count("`alphas`"), 1)


class PackInjectedOutputsTest(unittest.TestCase):
    def test_pack_outputs_render_when_scan_empty(self):
        scan = _scan()
        knowledge = {"pack_outputs": [
            {"file": "positive.dat", "meaning": "positive partons", "source": "main.cpp"},
        ]}
        md = generate.render_outputs(scan, knowledge)
        self.assertIn("positive.dat", md)
        self.assertIn("positive partons", md)


class PackCommandFallbackTest(unittest.TestCase):
    def test_pack_command_used_when_driver_cannot_resolve(self):
        scan = _scan()  # no primary_entry -> driver resolution yields None
        profile = {"driver": {"arg_map": {}}, "command": ["./lbt", "0"],
                   "tier1_output": "positive.dat"}
        argv = generate.profile_command_argv(scan, profile)
        self.assertEqual(argv, ["./lbt", "0"])

    def test_derived_command_preferred_over_pack_command(self):
        scan = _scan(primary_entry={"path": "run.py", "argv_names": ["jobid"],
                                    "argv_required": 1})
        profile = {"driver": {"arg_map": {}, "arg_defaults": {"jobid": "0"}},
                   "command": ["./should_not_be_used"]}
        argv = generate.profile_command_argv(scan, profile)
        self.assertEqual(argv[0], "python")
        self.assertNotIn("./should_not_be_used", argv)


class RunModesPackCommandTest(unittest.TestCase):
    def test_run_modes_shows_pack_command_with_provenance(self):
        scan = _scan()
        knowledge = {"run_profiles": {"minimal": {
            "driver": {"arg_map": {}}, "command": ["./lbt", "0"],
            "command_source": "agent-derived from main.cpp + Makefile",
            "tier1_output": "positive.dat", "tier2_observable": "dNdpT_parton"}}}
        md = generate.render_run_modes(scan, knowledge)
        self.assertIn("./lbt 0", md)
        self.assertNotIn("no entrypoint detected", md)
        self.assertIn("agent-derived", md)


if __name__ == "__main__":
    unittest.main()
