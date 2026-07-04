import importlib.util
import pathlib
import tempfile
import unittest

EXTRACTORS = pathlib.Path(__file__).resolve().parents[1] / "packs" / "lbt" / "extractors.py"

# Golden regression (A1): positive (10 cols: id px py pz E x y z t CAT) minus negative
# (9 cols). 3 positive, 1 negative -> net = 2; max pT = sqrt(6^2+8^2) = 10.0.
GOLDEN = {
    "observable": "dNdpT_parton",
    "out_subdir": "",
    "files": {
        "results_analysis/hydro_0/positive.dat": (
            "# 0 2\n21 3.0 4.0 0.0 5.0 0 0 0 0.6 1\n1 6.0 8.0 0.0 10.0 0 0 0 0.6 1\n"
            "# 1 1\n21 0.0 1.0 0.0 1.0 0 0 0 0.6 1\n"),
        "results_analysis/hydro_0/negative.dat": (
            "# 0 1\n21 0.0 1.0 0.0 1.0 0 0 0 0.6\n"),
    },
    "expect": {"n_positive": 3, "n_negative": 1, "n_net": 2, "pt_max": 10.0},
    "tol": 1e-5,
}


def _load():
    spec = importlib.util.spec_from_file_location("lbt_extractors", EXTRACTORS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class LbtExtractorTest(unittest.TestCase):
    def test_net_dndpt_positive_minus_negative(self):
        ex = _load()
        with tempfile.TemporaryDirectory() as tmp:
            run = pathlib.Path(tmp) / "results_analysis" / "hydro_0"
            run.mkdir(parents=True)
            # positive: id px py pz E x y z t CAT (10 cols); '#' = event separator
            (run / "positive.dat").write_text(
                "# 0 2\n"
                "21 3.0 4.0 0.0 5.0 0 0 0 0.6 1\n"      # pT = 5
                "1 6.0 8.0 0.0 10.0 0 0 0 0.6 1\n"      # pT = 10
                "# 1 1\n"
                "21 0.0 1.0 0.0 1.0 0 0 0 0.6 1\n",     # pT = 1
                encoding="utf-8")
            # negative: id px py pz E x y z t (9 cols), recoil-hole to subtract
            (run / "negative.dat").write_text(
                "# 0 1\n"
                "21 0.0 1.0 0.0 1.0 0 0 0 0.6\n",       # pT = 1
                encoding="utf-8")
            out = pathlib.Path(tmp) / "obs"
            res = ex.extract("dNdpT_parton", str(pathlib.Path(tmp)), str(out))
            self.assertEqual(res["values"]["n_positive"], 3)
            self.assertEqual(res["values"]["n_negative"], 1)
            self.assertEqual(res["values"]["n_net"], 2)   # 3 - 1
            self.assertAlmostEqual(res["values"]["pt_max"], 10.0, places=5)
            self.assertTrue(pathlib.Path(res["plot"]).exists())

    def test_net_falls_back_to_positive_when_no_negative(self):
        ex = _load()
        with tempfile.TemporaryDirectory() as tmp:
            run = pathlib.Path(tmp) / "results_analysis" / "hydro_0"
            run.mkdir(parents=True)
            (run / "positive.dat").write_text(
                "1 6.0 8.0 0.0 10.0 0 0 0 0.6 1\n", encoding="utf-8")
            res = ex.extract("dNdpT_parton", str(pathlib.Path(tmp)), str(pathlib.Path(tmp) / "o"))
            self.assertEqual(res["values"]["n_positive"], 1)
            self.assertEqual(res["values"]["n_negative"], 0)
            self.assertEqual(res["values"]["n_net"], 1)

    def test_per_event_normalization(self):
        # Two '#' event separators -> n_events == 2; the spectrum must be
        # divided by event count so alphas-scan points (possibly different
        # event counts) are comparable.
        ex = _load()
        with tempfile.TemporaryDirectory() as tmp:
            run = pathlib.Path(tmp) / "results_analysis" / "hydro_0"
            run.mkdir(parents=True)
            (run / "positive.dat").write_text(
                "# 0 1\n21 3.0 4.0 0.0 5.0 0 0 0 0.6 1\n"      # event 0: 1 parton
                "# 1 1\n1 6.0 8.0 0.0 10.0 0 0 0 0.6 1\n",     # event 1: 1 parton
                encoding="utf-8")
            res = ex.extract("dNdpT_parton", str(pathlib.Path(tmp)),
                             str(pathlib.Path(tmp) / "o"))
            self.assertEqual(res["values"]["n_events"], 2)
            # 2 net partons over 2 events -> 1.0 partons/event integrated
            self.assertAlmostEqual(res["values"]["net_per_event"], 1.0, places=6)

    def test_missing_negative_warns(self):
        ex = _load()
        with tempfile.TemporaryDirectory() as tmp:
            run = pathlib.Path(tmp) / "results_analysis" / "hydro_0"
            run.mkdir(parents=True)
            (run / "positive.dat").write_text(
                "1 6.0 8.0 0.0 10.0 0 0 0 0.6 1\n", encoding="utf-8")
            res = ex.extract("dNdpT_parton", str(pathlib.Path(tmp)),
                             str(pathlib.Path(tmp) / "o"))
            self.assertIn("warning", res["values"])
            self.assertIn("positive-only", res["values"]["warning"])

    def test_unknown_observable(self):
        ex = _load()
        with tempfile.TemporaryDirectory() as tmp:
            res = ex.extract("nope", tmp, tmp)
            self.assertIn("error", res)

    def test_missing_file(self):
        ex = _load()
        with tempfile.TemporaryDirectory() as tmp:
            res = ex.extract("dNdpT_parton", tmp, tmp)
            self.assertIn("error", res)


if __name__ == "__main__":
    unittest.main()
