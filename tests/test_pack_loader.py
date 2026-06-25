import pathlib
import tempfile
import unittest

from engine import pack_loader

FIX = pathlib.Path(__file__).resolve().parent / "fixtures" / "packs"


class PackLoaderTest(unittest.TestCase):
    def test_match_by_file_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "marker.txt").write_text("x", encoding="utf-8")
            scan = {"project_root": str(root), "readme_path": None}
            pack = pack_loader.select_pack(FIX, scan, root)
            self.assertIsNotNone(pack)
            self.assertEqual(pack["name"], "demo")
            self.assertIn("alpha", pack["knowledge"]["param_meaning"])

    def test_no_match_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            scan = {"project_root": str(root), "readme_path": None}
            self.assertIsNone(pack_loader.select_pack(FIX, scan, root))

    def test_uses_scan_effective_root_over_caller_root(self):
        # Caller passes the wrapper dir; the marker lives in the inner project
        # the scan descended into. select_pack must honor scan["project_root"].
        with tempfile.TemporaryDirectory() as tmp:
            wrapper = pathlib.Path(tmp)
            inner = wrapper / "Project"
            inner.mkdir()
            (inner / "marker.txt").write_text("x", encoding="utf-8")
            scan = {"project_root": str(inner), "readme_path": None}
            pack = pack_loader.select_pack(FIX, scan, wrapper)
            self.assertIsNotNone(pack)
            self.assertEqual(pack["name"], "demo")


if __name__ == "__main__":
    unittest.main()
