import json
import pathlib
import tempfile
import unittest

from engine import generate
from engine import scan as scanmod
from engine import pack_loader

URQMD = pathlib.Path("/home/qiwang/下载/scripts/urqmd-afterburner-nucleon-coalescence-main")
PACKS = pathlib.Path(__file__).resolve().parents[1] / "packs"


@unittest.skipUnless(URQMD.exists(), "urqmd checkout not present")
class UrqmdKnowledgeTest(unittest.TestCase):
    def _generate(self, out):
        sc = scanmod.scan_project(URQMD)
        pack = pack_loader.select_pack(PACKS, sc, URQMD)
        self.assertIsNotNone(pack, "urqmd pack must match")
        self.assertEqual(pack["name"], "urqmd")
        generate.generate(sc, pack, out)
        return sc

    def test_command_and_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            self._generate(out)
            prof = json.loads((out / "scripts/run_profile.json").read_text(encoding="utf-8"))
            self.assertEqual(prof["command_argv"],
                             ["./afterburner", "{oscar_file}", "particles_out.dat"])
            self.assertEqual(prof["tier1_output"], "particles_out.dat")
            self.assertIn("oscar_file", prof.get("inputs", {}))
            self.assertTrue(prof.get("build"))
            params = (out / "references/parameters.md").read_text(encoding="utf-8")
            self.assertIn("tim", params)         # injected pack_parameter
            outputs = (out / "references/outputs.md").read_text(encoding="utf-8")
            self.assertIn("particles_out.dat", outputs)


if __name__ == "__main__":
    unittest.main()
