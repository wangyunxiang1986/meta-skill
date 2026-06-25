import pathlib
import os
import tempfile
import unittest

from engine import generate, pack_loader
from engine import scan as scanmod

DEV = pathlib.Path(os.environ["CLVISC_TEST_ROOT"]) if os.environ.get("CLVISC_TEST_ROOT") else None
PACKS = pathlib.Path(__file__).resolve().parents[1] / "packs"


@unittest.skipUnless(DEV and DEV.exists(), "set CLVISC_TEST_ROOT to run CLVisc integration test")
class IntegrationGenerateTest(unittest.TestCase):
    def test_clvisc_pack_matched_and_enriched(self):
        scan = scanmod.scan_project(DEV)
        pack = pack_loader.select_pack(PACKS, scan, DEV)
        self.assertIsNotNone(pack)
        self.assertEqual(pack["name"], "clvisc")
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "skill"
            generate.generate(scan, pack, out)
            params = (out / "references" / "parameters.md").read_text(encoding="utf-8")
            self.assertIn("冻结温度", params)
            runmodes = (out / "references" / "run-modes.md").read_text(encoding="utf-8")
            self.assertIn("CLVisc.py", runmodes)
            self.assertTrue((out / "scripts" / "extractors.py").exists())
            self.assertTrue((out / "scripts" / "run_profile.json").exists())
            self.assertTrue((out / "scripts" / "run_launcher.py").exists())


if __name__ == "__main__":
    unittest.main()
