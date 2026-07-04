import pathlib
import subprocess
import sys
import tempfile
import unittest

from engine import generate


ENGINE_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _pack():
    return {"name": "demo", "extractors_path": None,
            "knowledge": {"run_profiles": {"minimal": {
                "driver": {"arg_map": {"config": ["cfg", "config"]},
                           "arg_defaults": {"default": "0"}},
                "tier1_output": "result.dat", "tier2_observable": "y"}}}}


def _scan():
    entry = {"path": "run.py", "cli_style": "argv", "argv_names": ["cfg"]}
    return {"project_root": "/x", "git": {}, "parameters": [], "output_files": [],
            "build_targets": [], "entrypoints": [entry], "primary_entry": entry,
            "directories": [], "file_counts": {}, "dependencies": []}


class ConfirmationGateGenerateTest(unittest.TestCase):
    def test_generate_emits_gate_files_and_skill_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "skill"
            generate.generate(_scan(), _pack(), out)
            self.assertTrue((out / "scripts" / "confirm.py").exists())
            gate = out / "references" / "confirmation.yaml"
            self.assertTrue(gate.exists())
            text = gate.read_text(encoding="utf-8")
            self.assertIn("parameter_meanings: no", text)
            self.assertIn("run_flow: no", text)
            self.assertIn("observable: no", text)
            skill_md = (out / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("## Confirmation Gate", skill_md)
            self.assertIn("scripts/confirm.py", skill_md)


class ConfirmCliTest(unittest.TestCase):
    def _skill(self, tmp):
        out = pathlib.Path(tmp) / "skill"
        generate.generate(_scan(), _pack(), out)
        return out

    def _run(self, skill, *args):
        return subprocess.run(
            [sys.executable, str(skill / "scripts" / "confirm.py"), *args],
            cwd=str(ENGINE_ROOT), capture_output=True, text=True)

    def test_status_unconfirmed_exits_3(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = self._skill(tmp)
            res = self._run(skill)
            self.assertEqual(res.returncode, 3)
            self.assertIn("UNCONFIRMED", res.stdout)

    def test_confirm_requires_by(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = self._skill(tmp)
            res = self._run(skill, "--confirm")
            self.assertEqual(res.returncode, 2)

    def test_confirm_then_status_exits_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = self._skill(tmp)
            done = self._run(skill, "--confirm", "--by", "Qi Wang")
            self.assertEqual(done.returncode, 0)
            res = self._run(skill)
            self.assertEqual(res.returncode, 0)
            self.assertIn("CONFIRMED by Qi Wang", res.stdout)


class RunGateTest(unittest.TestCase):
    """run.py must refuse to run while the gate is unconfirmed."""

    def _skill(self, tmp):
        out = pathlib.Path(tmp) / "skill"
        generate.generate(_scan(), _pack(), out)
        return out

    def _run_py(self, skill, *args):
        # minimal args; run.py should bail at the gate before reaching the launcher
        return subprocess.run(
            [sys.executable, str(skill / "scripts" / "run.py"), *args],
            cwd=str(ENGINE_ROOT), capture_output=True, text=True)

    def test_unconfirmed_run_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = self._skill(tmp)
            res = self._run_py(skill)
            self.assertEqual(res.returncode, 3)
            self.assertIn("CONFIRMATION GATE", res.stderr)

    def test_confirmed_run_passes_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = self._skill(tmp)
            subprocess.run(
                [sys.executable, str(skill / "scripts" / "confirm.py"),
                 "--confirm", "--by", "Qi Wang"],
                cwd=str(ENGINE_ROOT), capture_output=True, text=True)
            res = self._run_py(skill)
            # past the gate: no gate message; launcher then complains about its own
            # required args (--project-root/--work-dir/--run-profile), not the gate.
            self.assertNotIn("CONFIRMATION GATE", res.stderr)


if __name__ == "__main__":
    unittest.main()
