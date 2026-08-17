"""Column truth: recover an output file's column ORDER from an INDEPENDENT source --
the C++ writer's `<<` chain or the file's own header -- so it does not depend on any
model's reading. This is the ground truth a generated/hand-written extractor is checked
against (the thing the URQMD py-as-phi / pz-as-eta column bug got wrong).
"""
import unittest

from drafting import columns


class ColumnTruthTest(unittest.TestCase):
    def test_cpp_stream_recovers_order(self):
        line = ('positiveLBT<<LBT->KATT1[i]<<" "<<LBT->P[1][i]<<" "<<LBT->P[2][i]<<" "'
                '<<LBT->P[3][i]<<" "<<LBT->P[0][i]<<" "<<LBT->CAT[i]<<endl;')
        r = columns.column_truth(writer_line=line)
        self.assertEqual(r["paradigm"], "cpp_stream")
        self.assertEqual(r["fields"],
                         ["LBT->KATT1", "LBT->P[1]", "LBT->P[2]", "LBT->P[3]",
                          "LBT->P[0]", "LBT->CAT"])

    def test_commented_write_is_ignored(self):
        self.assertEqual(columns.parse_cpp_stream_write("// f<<a<<b<<endl;"), [])

    def test_leading_minus_is_a_sign_not_the_field_name(self):
        # a negative-record write (URQMD/LBT negative.dat: neg<<-P0[1]<<...) must still
        # map to the field 'P0[1]', so a unary minus is stripped from the token.
        line = 'negativeLBT<<-LBT->P0[1][i]<<" "<<-LBT->P0[2][i]<<endl;'
        self.assertEqual(columns.parse_cpp_stream_write(line),
                         ["LBT->P0[1]", "LBT->P0[2]"])

    def test_header_named_oscar(self):
        h = "#!OSCAR2013 particle_lists t x y z mass p0 px py pz pdg ID charge"
        r = columns.column_truth(header_line=h)
        self.assertEqual(r["paradigm"], "header_named")
        self.assertEqual(r["fields"][:4], ["t", "x", "y", "z"])
        self.assertIn("px", r["fields"])

    def test_header_kv_trento(self):
        r = columns.column_truth(header_kv_lines=["# b = 1", "# npart = 2", "# mult = 3"])
        self.assertEqual(r["paradigm"], "header_kv")
        self.assertEqual(r["fields"], ["b", "npart", "mult"])


if __name__ == "__main__":
    unittest.main()
