import pathlib
import tempfile
import unittest

from engine import scan


class OutputScanTest(unittest.TestCase):
    def test_outputs_and_build_targets_and_full_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            pkg = root / "pkg"
            pkg.mkdir()
            (pkg / "w.py").write_text(
                "import numpy as np\n"
                "np.savetxt('result.dat', x)\n", encoding="utf-8")
            (root / "engine_cmake").mkdir()
            (root / "engine_cmake" / "CMakeLists.txt").write_text("x\n", encoding="utf-8")
            outs = scan.discover_output_files_from_source(root, ["pkg"])
            self.assertIn("result.dat", outs)
            targets = scan.build_targets(root)
            self.assertIn("engine_cmake", targets)
            full = scan.scan_project(root)
            for key in ("entrypoints", "parameters", "output_files", "build_targets", "git"):
                self.assertIn(key, full)


if __name__ == "__main__":
    unittest.main()
