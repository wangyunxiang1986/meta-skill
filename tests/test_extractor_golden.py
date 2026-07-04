"""Meta-test (A1): every knowledge pack that ships an ``extractors.py`` MUST carry a
golden regression -- a real-format sample with KNOWN expected values -- so a mis-parse
like the URQMD column bug (py read as phi, pz read as eta; "T2 passed" but the physics
was wrong) fails loudly instead of silently producing a bogus number.

Convention: each pack's ``tests/test_pack_<name>_extractors.py`` module declares a
module-level ``GOLDEN`` dict::

    GOLDEN = {
        "observable": "dNchdeta",          # what to extract
        "out_subdir": "",                  # extract(out_dir = <tmp>/out_subdir)
        "files": {"relpath": "content"},   # sample files written under <tmp>
        "expect": {"key": value},          # expected result["values"][key]
        "tol": 1e-6,                       # abs tolerance
    }

This meta-test discovers every pack with an extractor, requires that GOLDEN, runs the
real extractor against it, and checks the computed values. It is model-agnostic: adding
a pack automatically requires a golden, with no change here.
"""
import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKS = ROOT / "packs"
TESTS = ROOT / "tests"


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _packs_with_extractors():
    return sorted(p.parent.name for p in PACKS.glob("*/extractors.py")
                  if p.parent.name != "_template")


class ExtractorGoldenTest(unittest.TestCase):
    def test_there_is_at_least_one_extractor_pack(self):
        # guard against the discovery silently matching nothing
        self.assertTrue(_packs_with_extractors())

    def test_every_extractor_pack_declares_a_golden(self):
        for name in _packs_with_extractors():
            with self.subTest(pack=name):
                tf = TESTS / ("test_pack_%s_extractors.py" % name)
                self.assertTrue(tf.exists(),
                                "pack '%s' ships extractors.py but has no %s" % (name, tf.name))
                mod = _load_module(tf, "golden_decl_%s" % name)
                self.assertTrue(hasattr(mod, "GOLDEN"),
                                "%s must define a module-level GOLDEN dict "
                                "(real-format sample + expected values)" % tf.name)

    def test_golden_values_match(self):
        for name in _packs_with_extractors():
            with self.subTest(pack=name):
                g = _load_module(TESTS / ("test_pack_%s_extractors.py" % name),
                                 "golden_val_%s" % name).GOLDEN
                ex = _load_module(PACKS / name / "extractors.py", "ex_%s" % name)
                with tempfile.TemporaryDirectory() as tmp:
                    root = pathlib.Path(tmp)
                    for rel, content in g["files"].items():
                        f = root / rel
                        f.parent.mkdir(parents=True, exist_ok=True)
                        f.write_text(content, encoding="utf-8")
                    out_dir = root / g.get("out_subdir", "")
                    res = ex.extract(g["observable"], str(out_dir), str(root / "_analysis"))
                    self.assertNotIn("error", res, "%s: %s" % (name, res.get("error")))
                    vals = res.get("values", {})
                    tol = g.get("tol", 1e-6)
                    for key, want in g["expect"].items():
                        self.assertIn(key, vals, "%s: extractor did not return '%s'" % (name, key))
                        self.assertAlmostEqual(
                            vals[key], want, delta=tol,
                            msg="%s.%s: got %s, want %s (golden mismatch -- a format/parse "
                                "regression?)" % (name, key, vals.get(key), want))


if __name__ == "__main__":
    unittest.main()
