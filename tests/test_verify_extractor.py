"""Non-circular strong verification of an extractor. A discriminating probe (each column
a distinct value) plus a column truth lets us reject a parser that reads the WRONG column
(the URQMD-class bug) even if it looks plausible and would otherwise "pass T2".

Scope, stated honestly: this catches a column-INDEX error (parser reads a different
column than the truth dictates). It does NOT catch a physics_map mislabel (naming a
field the wrong role), since expectation and extractor share the map -- that is a
semantic input for human confirmation.
"""
import math
import pathlib
import tempfile
import unittest

from drafting import verify_extractor

_GOOD = '''\
import math, os
def extract(obs, out_dir, an):
    path = [os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.endswith(".dat")][0]
    pts = []
    for line in open(path):
        if line.startswith("#"): continue
        p = line.split()
        if len(p) < 6: continue
        px, py = float(p[3]), float(p[4])          # correct: px=col3, py=col4
        pts.append(math.sqrt(px*px + py*py))
    return {"observable": obs, "values": {"pt_max": max(pts) if pts else 0}}
'''
_BAD = _GOOD.replace("float(p[3]), float(p[4])", "float(p[4]), float(p[5])")  # col shift


class VerifyExtractorTest(unittest.TestCase):
    FIELDS = ["id", "charge", "mass", "px", "py", "pz", "t", "x", "y", "z"]
    PMAP = {"px": "px", "py": "py", "pz": "pz"}

    def _write(self, tmp, src):
        p = pathlib.Path(tmp) / "ext.py"
        p.write_text(src, encoding="utf-8")
        return str(p)

    def test_correct_extractor_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = verify_extractor.verify(self._write(tmp, _GOOD), self.FIELDS, self.PMAP,
                                        "dNdpT", "particles_out.dat", "pt_max")
            self.assertTrue(r["ok"], r)
            self.assertAlmostEqual(r["expected"], math.sqrt(7 * 7 + 11 * 11), places=6)

    def test_column_shifted_extractor_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = verify_extractor.verify(self._write(tmp, _BAD), self.FIELDS, self.PMAP,
                                        "dNdpT", "particles_out.dat", "pt_max")
            self.assertFalse(r["ok"], r)          # the URQMD-class bug is caught
            self.assertNotAlmostEqual(r["got"], r["expected"], places=3)


if __name__ == "__main__":
    unittest.main()
