import importlib.util
import pathlib
import tempfile
import unittest

EXT = pathlib.Path(__file__).resolve().parents[1] / "packs" / "smash" / "extractors.py"

# OSCAR2013 particle_lists: '# event N out M' + 't x y z mass p0 px py pz pdg ID charge'
SAMPLE = (
    "#!OSCAR2013 particle_lists t x y z mass p0 px py pz pdg ID charge\n"
    "# Units: fm fm fm fm GeV GeV GeV GeV GeV none none e\n"
    "# SMASH-3.1\n"
    "# event 0 out 3\n"
    "200 0 0 0 0.139 0.5 0.3 0.1 0.2 211 0 1\n"
    "200 0 0 0 0.139 0.5 -0.3 0.1 0.2 -211 1 -1\n"
    "200 0 0 0 0.0 0.4 0.2 0.0 0.1 22 2 0\n"
    "# event 1 out 2\n"
    "200 0 0 0 0.938 1.0 0.5 0.2 0.3 2212 0 1\n"
    "200 0 0 0 0.139 0.3 0.1 -0.1 0.2 211 1 1\n"
)

# Golden regression (A1): controlled OSCAR2013 sample (t x y z mass p0 px py pz pdg
# ID charge). Two charged partons share the SAME pseudorapidity eta=asinh(4/3)=1.0986
# via different pz (4 and 8) -> they pile into one eta bin -> dN/deta peak = 2/(1 ev *
# 0.25) = 8.0. This is bug-sensitive: an `eta=pz` mis-parse would put them at eta 4 & 8
# (8 is outside [-5,5)) -> peak halves. The neutral (charge 0, p<=|pz|) is excluded.
GOLDEN = {
    "observable": "dNchdeta",
    "out_subdir": "",
    "files": {"particle_lists.oscar": (
        "# event 1 out 3\n"
        "0 0 0 0 0.138 5.0 3.0 0.0 4.0 211 1 1\n"
        "0 0 0 0 0.138 10.0 6.0 0.0 8.0 211 2 1\n"
        "0 0 0 0 0.0 1.0 0.0 0.0 1.0 22 3 0\n")},
    "expect": {"n_events": 1, "n_charged": 2, "dNdeta_peak": 8.0},
    "tol": 1e-6,
}


def _load():
    spec = importlib.util.spec_from_file_location("smash_ext", EXT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SmashExtractorTest(unittest.TestCase):
    def test_dNchdeta_and_v2(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            (out / "particle_lists.oscar").write_text(SAMPLE, encoding="utf-8")
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
