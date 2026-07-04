import importlib.util
import pathlib
import tempfile
import unittest

EX = pathlib.Path(__file__).resolve().parents[1] / "packs" / "clvisc" / "extractors.py"

# Golden regression (A1): dN/deta table (eta value) -> the mid-rapidity value at
# eta=0 must be read back exactly.
GOLDEN = {
    "observable": "dNchdeta",
    "out_subdir": "event0",
    "files": {"event0/dNdEta_mc_charged.dat": "-1 100\n0 150\n1 120\n"},
    "expect": {"eta0": 150.0},
    "tol": 1e-3,
}


def _load():
    spec = importlib.util.spec_from_file_location("clvisc_ex", EX)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ClviscExtractorsTest(unittest.TestCase):
    def test_extract_dNchdeta(self):
        ex = _load()
        with tempfile.TemporaryDirectory() as tmp:
            run = pathlib.Path(tmp) / "event0"
            run.mkdir()
            (run / "dNdEta_mc_charged.dat").write_text(
                "-1 100\n0 150\n1 120\n", encoding="utf-8")
            out = pathlib.Path(tmp) / "an"
            res = ex.extract("dNchdeta", str(run), str(out))
            self.assertAlmostEqual(res["values"]["eta0"], 150.0, places=3)
            self.assertTrue(pathlib.Path(res["plot"]).exists())

    def test_fit_returns_coeffs(self):
        ex = _load()
        with tempfile.TemporaryDirectory() as tmp:
            res = ex.fit([{"ETAOS_YMIN": 0.08, "v2": 0.05},
                          {"ETAOS_YMIN": 0.16, "v2": 0.03}], "ETAOS_YMIN", "v2", tmp)
            self.assertIn("poly_coeffs", res)
            self.assertEqual(len(res["poly_coeffs"]), 2)


if __name__ == "__main__":
    unittest.main()
