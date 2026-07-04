# When you fill this in, you MUST also add a golden regression (A1): a real-format
# output sample with hand-computed expected values, declared as a module-level GOLDEN
# dict in tests/test_pack_<name>_extractors.py. tests/test_extractor_golden.py discovers
# it, runs this extractor against the sample, and checks the values -- so a parse/column
# regression (see the URQMD py-as-phi / pz-as-eta bug) fails loudly instead of quietly
# producing a wrong number that still "passes T2". A pack with extractors.py but no
# GOLDEN will fail the meta-test.
def extract(observable, run_dir, out_dir):
    raise NotImplementedError("fill in for this model")


def fit(scan_results, param, observable, out_dir):
    raise NotImplementedError("fill in for this model")
