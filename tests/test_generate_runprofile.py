import json
import pathlib
import tempfile
import unittest

from engine import generate


class RunProfileEmitTest(unittest.TestCase):
    def test_emits_run_profile_and_launcher(self):
        pack = {"name": "demo", "extractors_path": None,
                "knowledge": {"run_profiles": {"minimal": {
                    "driver": {"arg_map": {"config": ["cfg", "config"]},
                               "arg_defaults": {"default": "0"}},
                    "tier1_output": "result.dat", "tier2_observable": "y"}}}}
        entry = {"path": "run.py", "cli_style": "argv", "argv_names": ["cfg", "n"]}
        scan = {"parameters": [], "output_files": [], "build_targets": [],
                "entrypoints": [entry], "primary_entry": entry}
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "skill"
            generate.generate(scan, pack, out)
            prof = json.loads((out / "scripts" / "run_profile.json").read_text(encoding="utf-8"))
            # command derived from the scanned entry, not hardcoded in the pack
            self.assertEqual(prof["command_argv"], ["python", "run.py", "{config}", "0"])
            self.assertEqual(prof["tier1_output"], "result.dat")
            self.assertTrue((out / "scripts" / "run_launcher.py").exists())


if __name__ == "__main__":
    unittest.main()
