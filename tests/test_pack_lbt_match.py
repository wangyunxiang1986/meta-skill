import pathlib
import tempfile
import unittest

from engine import pack_loader

PACKS = pathlib.Path(__file__).resolve().parents[1] / "packs"


class LbtMatchTest(unittest.TestCase):
    def test_matches_codes_dir_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "LBT.cpp").write_text("int main(int argc, char**argv){}\n", encoding="utf-8")
            (root / "LBTinput.txt").write_text("LBTswitch\n1\n", encoding="utf-8")
            scan = {"readme_path": None}
            pack = pack_loader.select_pack(PACKS, scan, root)
            self.assertIsNotNone(pack)
            self.assertEqual(pack["name"], "lbt")

    def test_no_match_generic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            scan = {"readme_path": None}
            pack = pack_loader.select_pack(PACKS, scan, root)
            self.assertNotEqual((pack or {}).get("name"), "lbt")


if __name__ == "__main__":
    unittest.main()
