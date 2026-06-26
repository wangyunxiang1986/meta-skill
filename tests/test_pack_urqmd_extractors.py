import importlib.util
import pathlib
import tempfile
import unittest

EXT = pathlib.Path(__file__).resolve().parents[1] / "packs" / "urqmd" / "extractors.py"

SAMPLE = (
    "# event 1 particles 3\n"
    "211 1 0.139 0.5 0.10 0.20\n"
    "-211 -1 0.139 0.6 1.50 -0.30\n"
    "22 0 0.0 0.4 2.00 0.00\n"
    "# event 2 particles 2\n"
    "2212 1 0.938 0.8 0.50 0.50\n"
    "211 1 0.139 0.3 2.50 -0.50\n"
)


def _load():
    spec = importlib.util.spec_from_file_location("urqmd_ext", EXT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class UrqmdExtractorTest(unittest.TestCase):
    def test_dNchdeta_and_v2(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            (out / "particles_out.dat").write_text(SAMPLE, encoding="utf-8")
            res = _load().extract("dNchdeta", str(out), str(out / "analysis"))
            self.assertNotIn("error", res)
            self.assertEqual(res["values"]["n_events"], 2)
            self.assertEqual(res["values"]["n_charged"], 4)   # photon excluded
            self.assertIn("v2", res["values"])
            self.assertTrue(pathlib.Path(res["plot"]).exists())

    def test_missing_file_is_graceful(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = _load().extract("dNchdeta", tmp, str(pathlib.Path(tmp) / "a"))
            self.assertIn("error", res)


if __name__ == "__main__":
    unittest.main()
