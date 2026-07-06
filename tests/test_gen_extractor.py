"""Closing the loop: synthesise an extractor from a column truth, then strong-verify it.

The extractor's column indices are filled from drafting.columns' recovered order (from
the C++ writer chain / file header), not chosen freely. drafting.verify_extractor then
runs a discriminating probe. Scope, stated honestly:
  * CATCHES a column-INDEX error -- a generated (or hand-written) parser reading the
    wrong column (the URQMD-class bug). This is the failure codegen could introduce.
  * does NOT catch a physics_map MISLABEL (naming a field the wrong role): expectation
    and extractor share the map. That is a semantic input for human confirmation.
"""
import pathlib
import tempfile
import unittest

from drafting import columns, gen_extractor, verify_extractor

# LBT writer chain -> the independent column truth
LBT_WRITER = ('positiveLBT<<LBT->KATT1[i]<<" "<<LBT->P[1][i]<<" "<<LBT->P[2][i]<<" "'
              '<<LBT->P[3][i]<<" "<<LBT->P[0][i]<<" "<<LBT->CAT[i]<<endl;')
FIELDS = columns.column_truth(writer_line=LBT_WRITER)["fields"]
GOOD_MAP = {"LBT->KATT1": "id", "LBT->P[1]": "px", "LBT->P[2]": "py",
            "LBT->P[3]": "pz", "LBT->CAT": "charge"}


class GenExtractorTest(unittest.TestCase):
    def test_generated_source_uses_truth_indices(self):
        src = gen_extractor.generate_extractor_source(FIELDS, GOOD_MAP, "positive.dat")
        # P[1]=index1 -> px reads p[1]; P[3]=index3 -> pz reads p[3]
        self.assertIn("float(p[1]), float(p[2]), float(p[3])", src)
        compile(src, "<gen>", "exec")                      # generated code is valid Python

    def test_generate_and_verify_accepts_faithful_extractor(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = gen_extractor.generate_and_verify(
                FIELDS, GOOD_MAP, "positive.dat", dest_path=str(pathlib.Path(tmp) / "e.py"))
            self.assertTrue(r["generated"])
            self.assertTrue(r["verified"], r["checks"])
            self.assertTrue(r["checks"]["pt_max"]["ok"])
            self.assertTrue(r["checks"]["eta_max"]["ok"])
            self.assertIn("written_to", r)                 # only written when verified

    def test_verify_rejects_a_column_index_error(self):
        # A hand-broken extractor that reads the WRONG columns (px from the pz column
        # etc.) must be rejected -- this is the URQMD-class bug the probe exists to catch.
        wrong = '''
import math, os
def extract(o, d, a):
    f = [os.path.join(d, x) for x in os.listdir(d) if x.endswith(".dat")][0]
    pts = []
    for line in open(f):
        if line.startswith("#"): continue
        p = line.split()
        if len(p) < 6: continue
        px, py = float(p[2]), float(p[3])          # WRONG: truth has px=1, py=2
        pts.append(math.sqrt(px*px + py*py))
    return {"observable": o, "values": {"pt_max": max(pts)}}
'''
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "wrong.py"
            p.write_text(wrong, encoding="utf-8")
            r = verify_extractor.verify(str(p), FIELDS, GOOD_MAP, "dNdpT",
                                        "positive.dat", "pt_max")
            self.assertFalse(r["ok"])
            self.assertNotAlmostEqual(r["got"], r["expected"], places=3)

    def test_missing_required_role_hands_off(self):
        # No px in the map -> codegen refuses (a human must supply it), not silently wrong.
        r = gen_extractor.generate_and_verify(FIELDS, {"LBT->KATT1": "id"}, "positive.dat")
        self.assertFalse(r["generated"])
        self.assertIn("hand off", r["hint"])

    def test_header_kv_generator_is_name_addressed(self):
        # The second paradigm now lives here too: a '# key = value' header reader keyed by
        # NAME, so no physics_map and no positional column to mis-read.
        src = gen_extractor.generate_header_kv_extractor_source(r"\d\.dat")
        self.assertNotIn("__PATTERN__", src)               # pattern substituted in
        self.assertIn(r"\d\.dat", src)
        compile(src, "<gen-kv>", "exec")                   # valid Python

    def test_generate_from_truth_dispatches_by_paradigm(self):
        kv = gen_extractor.generate_from_truth(
            {"paradigm": "header_kv", "fields": ["mult"]}, file_pattern=r"\d\.dat")
        self.assertEqual(kv["addressing"], "name")
        compile(kv["source"], "<kv>", "exec")
        col = gen_extractor.generate_from_truth(
            {"paradigm": "cpp_stream", "fields": FIELDS},
            physics_map=GOOD_MAP, out_filename="positive.dat")
        self.assertEqual(col["addressing"], "position")
        self.assertIn("float(p[1]), float(p[2]), float(p[3])", col["source"])

    def test_columnar_paradigm_without_physics_map_hands_off(self):
        # position-addressed output + no physics_map -> loud hand-off, never a guess.
        with self.assertRaises(KeyError):
            gen_extractor.generate_from_truth(
                {"paradigm": "cpp_stream", "fields": FIELDS}, out_filename="positive.dat")
        with self.assertRaises(ValueError):
            gen_extractor.generate_from_truth({"paradigm": "unknown", "fields": []})


if __name__ == "__main__":
    unittest.main()
