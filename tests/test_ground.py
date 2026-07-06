"""Tests for the P1 grounding tools: capture the real output format and locate the
writer code that reveals the column order -- the ground truth a drafter needs so the
observable layer is derived, not imagined (the anti-URQMD-column-bug pass)."""
import pathlib
import tempfile
import unittest

from drafting import ground


class CaptureSampleTest(unittest.TestCase):
    def test_separates_header_from_data_and_counts_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            (out / "positive.dat").write_text(
                "# event 0 3\n"                              # header/comment
                "21 3.0 4.0 0.0 5.0 0 0 0 0.6 1\n"           # 10-col data row
                "1 6.0 8.0 0.0 10.0 0 0 0 0.6 1\n",
                encoding="utf-8")
            s = ground.capture_sample(str(out), "positive.dat")
            self.assertTrue(s["found"])
            self.assertEqual(s["n_columns"], 10)             # real column count
            self.assertIn("# event 0 3", s["header_lines"])
            self.assertEqual(len(s["data_head"]), 2)

    def test_found_via_walk_and_missing_is_graceful(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = pathlib.Path(tmp) / "run" / "hydro_0"
            nested.mkdir(parents=True)
            (nested / "out.dat").write_text("1 2 3\n", encoding="utf-8")
            self.assertTrue(ground.capture_sample(tmp, "out.dat")["found"])
            self.assertFalse(ground.capture_sample(tmp, "nope.dat")["found"])


class LocateWriterTest(unittest.TestCase):
    def test_ranks_the_column_revealing_write_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "main.cpp").write_text(
                'ofstream f("out.dat");\n'                                  # names the file
                '// f<<id<<" "<<a<<" "<<b<<endl;   // old, commented\n'      # commented write
                'cout<<"debug"<<endl;\n'                                    # noise, few fields
                'f<<id<<" "<<px<<" "<<py<<" "<<pz<<" "<<E<<endl;\n',        # the real record write
                encoding="utf-8")
            w = ground.locate_writer(str(root), "out.dat")
            self.assertTrue(any(h["line"] == 1 for h in w["named_at"]))     # declaration found
            top = w["field_writes"][0]
            self.assertEqual(top["line"], 4)                               # uncommented, most fields
            self.assertFalse(top["commented"])
            self.assertIn("px", top["text"])

    def test_savetxt_python_writer_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "w.py").write_text(
                "import numpy as np\nnp.savetxt('spec.dat', arr)\n", encoding="utf-8")
            w = ground.locate_writer(str(root), "spec.dat")
            self.assertTrue(w["field_writes"])
            self.assertIn("savetxt", w["field_writes"][0]["text"])


class GroundingBriefTest(unittest.TestCase):
    def test_brief_combines_sample_writer_and_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "main.cpp").write_text(
                'ofstream f("out.dat");\nf<<a<<" "<<b<<" "<<c<<endl;\n', encoding="utf-8")
            run = root / "run"
            run.mkdir()
            (run / "out.dat").write_text("1 2 3\n", encoding="utf-8")
            g = ground.observable_grounding(str(root), str(run), "out.dat")
            self.assertTrue(g["sample"]["found"])
            self.assertEqual(g["sample"]["n_columns"], 3)
            self.assertTrue(g["writer"]["named_at"])
            self.assertTrue(g["gaps_to_fill"])
            md = ground.to_markdown(g)
            self.assertIn("column ORDER", md)
            self.assertIn("out.dat", md)


if __name__ == "__main__":
    unittest.main()
