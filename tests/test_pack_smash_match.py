import pathlib
import tempfile
import unittest

from engine import scan as scanmod
from engine import pack_loader

PACKS = pathlib.Path(__file__).resolve().parents[1] / "packs"


class SmashMatchTest(unittest.TestCase):
    def test_matches_smash_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "smash.cc").write_text("int main(){}\n", encoding="utf-8")
            (root / "README.md").write_text("# SMASH\nhadronic transport\n", encoding="utf-8")
            sc = scanmod.scan_project(root)
            pack = pack_loader.select_pack(PACKS, sc, root)
            self.assertIsNotNone(pack)
            self.assertEqual(pack["name"], "smash")

    def test_does_not_match_plain_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "main.py").write_text("import sys\nx = sys.argv[1]\n", encoding="utf-8")
            sc = scanmod.scan_project(root)
            pack = pack_loader.select_pack(PACKS, sc, root)
            self.assertIsNone(pack)


if __name__ == "__main__":
    unittest.main()
