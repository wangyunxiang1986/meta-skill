import json
import pathlib
import tempfile
import unittest

from engine import generate
from engine import scan as scanmod
from engine import pack_loader

SMASH = pathlib.Path("/home/qiwang/smash1/smash")
PACKS = pathlib.Path(__file__).resolve().parents[1] / "packs"


@unittest.skipUnless(SMASH.exists(), "smash checkout not present")
class SmashKnowledgeTest(unittest.TestCase):
    def _generate(self, out):
        sc = scanmod.scan_project(SMASH)
        pack = pack_loader.select_pack(PACKS, sc, SMASH)
        self.assertIsNotNone(pack, "smash pack must match")
        self.assertEqual(pack["name"], "smash")
        generate.generate(sc, pack, out)
        return sc

    def test_command_and_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            self._generate(out)
            prof = json.loads((out / "scripts/run_profile.json").read_text(encoding="utf-8"))
            self.assertEqual(prof["command_argv"],
                             ["./smash", "-i", "config.yaml",
                              "-p", "{root}/input/particles.txt",
                              "-d", "{root}/input/decaymodes.txt",
                              "-o", "{work}/out", "-f", "-q"])
            self.assertEqual(prof["tier1_output"], "particle_lists.oscar")
            self.assertIn("list_dir", prof.get("inputs", {}))
            params = (out / "references/parameters.md").read_text(encoding="utf-8")
            self.assertIn("Nevents", params)         # injected pack_parameter
            outputs = (out / "references/outputs.md").read_text(encoding="utf-8")
            self.assertIn("particle_lists.oscar", outputs)


if __name__ == "__main__":
    unittest.main()
