import importlib.util
import pathlib
import tempfile
import unittest

EXT = pathlib.Path(__file__).resolve().parents[1] / "packs" / "trento" / "extractors.py"

# Golden regression (A1): two TRENTo grid files whose header 'mult' values are 10 and
# 30 -> mean_mult = 20.0 (reasoned independently of the extractor). The header key must
# be read by NAME, so a column/format regression breaks this.
GOLDEN = {
    "observable": "mult",
    "out_subdir": "",
    "files": {
        "0.dat": "# event 0\n# b     = 5.0\n# npart = 100\n# mult  = 10.0\n# e2    = 0.2\n1 2\n3 4\n",
        "1.dat": "# event 1\n# b     = 8.0\n# npart = 60\n# mult  = 30.0\n# e2    = 0.4\n5 6\n7 8\n",
    },
    "expect": {"n_events": 2, "mean_mult": 20.0, "min_mult": 10.0, "max_mult": 30.0},
    "tol": 1e-6,
}


def _load():
    spec = importlib.util.spec_from_file_location("trento_ext", EXT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TrentoExtractorTest(unittest.TestCase):
    def test_mean_multiplicity_from_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            for rel, content in GOLDEN["files"].items():
                (out / rel).write_text(content, encoding="utf-8")
            res = _load().extract("mult", str(out), str(out / "an"))
            self.assertNotIn("error", res)
            self.assertEqual(res["values"]["n_events"], 2)
            self.assertAlmostEqual(res["values"]["mean_mult"], 20.0, places=6)
            self.assertTrue(pathlib.Path(res["plot"]).exists())

    def test_eccentricity_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            for rel, content in GOLDEN["files"].items():
                (out / rel).write_text(content, encoding="utf-8")
            res = _load().extract("e2", str(out), str(out / "an2"))
            # e2 values 0.2 and 0.4 -> mean 0.3 (read by header name, not position)
            self.assertAlmostEqual(res["values"]["mean_e2"], 0.3, places=6)

    def test_missing_is_graceful(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = _load().extract("mult", tmp, tmp)
            self.assertIn("error", res)


if __name__ == "__main__":
    unittest.main()
