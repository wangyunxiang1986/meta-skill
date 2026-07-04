import importlib.util
import math
import pathlib
import tempfile
import unittest

EXT = pathlib.Path(__file__).resolve().parents[1] / "packs" / "urqmd" / "extractors.py"

# Golden regression (A1): id charge mass px py pz t x y z. Two charged partons share
# the SAME eta=asinh(4/3)=1.0986 via different pz (4 and 8) -> they pile into one bin
# -> dN/deta peak = 2/(1 event * 0.25) = 8.0. Bug-sensitive: the actual URQMD bug read
# pz as eta, which would place them at eta 4 & 8 (8 outside [-5,5)) -> peak halves to 4.
GOLDEN = {
    "observable": "dNchdeta",
    "out_subdir": "",
    "files": {"particles_out.dat": (
        "# event 1 particles 3\n"
        "211 1 0.139 3.0 0.0 4.0 0 0 0 0\n"
        "211 1 0.139 6.0 0.0 8.0 0 0 0 0\n"
        "22 0 0.0 1.0 1.0 1.0 0 0 0 0\n")},
    "expect": {"n_events": 1, "n_charged": 2, "dNdeta_peak": 8.0},
    "tol": 1e-6,
}

# Real output columns: id charge mass px py pz t x y z (10 cols). eta/phi/pT are
# derived from px,py,pz -- NOT columns 4/5 directly (that was the parsing bug).
SAMPLE = (
    "# event 1 particles 3\n"
    "211 1 0.139 3.0 0.0 4.0 0 0 0 0\n"      # px=3,py=0,pz=4 -> eta=0.5ln9=1.0986, phi=0
    "-211 -1 0.139 0.0 2.0 0.0 0 0 0 0\n"    # px=0,py=2,pz=0 -> eta=0, phi=pi/2
    "22 0 0.0 1.0 1.0 0.0 0 0 0 0\n"         # photon (charge 0) -> excluded
    "# event 2 particles 2\n"
    "2212 1 0.938 1.0 0.0 0.0 0 0 0 0\n"     # px=1,py=0,pz=0 -> eta=0, phi=0
    "211 1 0.139 0.0 0.0 5.0 0 0 0 0\n"      # forward, large +eta
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

    def test_parse_derives_eta_phi_from_momentum(self):
        """Regression: eta/phi must come from (px,py,pz), not raw columns 4/5."""
        mod = _load()
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "particles_out.dat"
            p.write_text("# event 1 particles 1\n211 1 0.139 3.0 0.0 4.0 0 0 0 0\n",
                         encoding="utf-8")
            events = mod._parse(str(p))
            self.assertEqual(len(events), 1)
            charge, phi, eta = events[0][0]
            self.assertEqual(charge, 1)
            self.assertAlmostEqual(eta, 0.5 * math.log(9.0), places=4)   # ~1.0986
            self.assertAlmostEqual(phi, 0.0, places=6)                    # atan2(0,3)

    def test_missing_file_is_graceful(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = _load().extract("dNchdeta", tmp, str(pathlib.Path(tmp) / "a"))
            self.assertIn("error", res)


if __name__ == "__main__":
    unittest.main()
