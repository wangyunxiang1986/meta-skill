import pathlib
import os
import unittest

from engine import pack_loader, understanding
from engine import scan as scanmod

DEV = pathlib.Path(os.environ["CLVISC_TEST_ROOT"]) if os.environ.get("CLVISC_TEST_ROOT") else None
PACKS = pathlib.Path(__file__).resolve().parents[1] / "packs"


@unittest.skipUnless(DEV and DEV.exists(), "set CLVISC_TEST_ROOT to run CLVisc integration test")
class IntegrationUnderstandingTest(unittest.TestCase):
    def test_understanding_uses_clvisc_meanings(self):
        scan = scanmod.scan_project(DEV)
        pack = pack_loader.select_pack(PACKS, scan, DEV)
        md = understanding.render_project_understanding(scan, pack)
        self.assertIn("clvisc", md)
        self.assertIn("冻结温度", md)
        self.assertIn("source-derived", md.lower())


if __name__ == "__main__":
    unittest.main()
