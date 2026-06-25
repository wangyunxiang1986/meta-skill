import pathlib
import tempfile
import unittest

from engine import pack_loader

PACKS = pathlib.Path(__file__).resolve().parents[1] / "packs"


class ClviscMatchTest(unittest.TestCase):
    def test_matches_pyvisc_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "pyvisc").mkdir()
            (root / "pyvisc" / "config.py").write_text("def read_config(p): ...\n", encoding="utf-8")
            scan = {"readme_path": None}
            pack = pack_loader.select_pack(PACKS, scan, root)
            self.assertIsNotNone(pack)
            self.assertEqual(pack["name"], "clvisc")

    def test_no_match_generic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            scan = {"readme_path": None}
            self.assertIsNone(pack_loader.select_pack(PACKS, scan, root))

    def test_readme_keyword_alone_does_not_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "README.md").write_text("This document mentions CLVisc as an example.\n",
                                            encoding="utf-8")
            scan = {"readme_path": "README.md", "project_root": str(root)}
            self.assertIsNone(pack_loader.select_pack(PACKS, scan, root))


if __name__ == "__main__":
    unittest.main()
