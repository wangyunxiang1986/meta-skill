"""Sanity tests for the pack-generator benchmark (P0). These pin the scorer's own
behaviour using the four hand-written packs as ground truth: a pack scored against
itself is near-perfect, a foreign pack scores low, and dropping fields lowers the
score. This is what lets us later trust the benchmark to grade LLM-drafted packs.
"""
import pathlib
import tempfile
import unittest

import yaml

from benchmark import pack_score

REPO = pathlib.Path(__file__).resolve().parents[1]
PACKS = REPO / "packs"
MODELS = [p.name for p in sorted(PACKS.glob("*")) if (p / "knowledge.yaml").exists()
          and p.name != "_template"]


class PackBenchmarkTest(unittest.TestCase):
    def test_there_are_reference_packs(self):
        self.assertTrue(MODELS)

    def test_identity_is_near_perfect(self):
        # a hand-written pack scored against itself: the objective dimensions
        # (extractor reproduces its own golden, run recipe, param coverage) are exact.
        for m in MODELS:
            with self.subTest(pack=m):
                r = pack_score.score_pack(PACKS / m, m)
                self.assertEqual(r["dimensions"]["extractor"], 1.0)
                self.assertEqual(r["dimensions"]["run_recipe"], 1.0)
                self.assertEqual(r["dimensions"]["params"], 1.0)
                self.assertEqual(r["dimensions"]["outputs"], 1.0)
                self.assertGreaterEqual(r["aggregate"], 0.9)

    def test_foreign_pack_scores_low(self):
        # smash's extractor cannot parse urqmd's output, its params/markers differ ->
        # the discriminating dimensions collapse and the aggregate is well below identity.
        r = pack_score.score_pack(PACKS / "smash", "urqmd")
        self.assertEqual(r["dimensions"]["extractor"], 0.0)
        self.assertEqual(r["dimensions"]["params"], 0.0)
        self.assertEqual(r["dimensions"]["manifest"], 0.0)
        self.assertLess(r["aggregate"], 0.5)

    def test_dropping_fields_lowers_score(self):
        identity = pack_score.score_pack(PACKS / "urqmd", "urqmd")["aggregate"]
        k = yaml.safe_load((PACKS / "urqmd" / "knowledge.yaml").read_text(encoding="utf-8"))
        for f in ("description", "intent_rules", "param_constraints", "demos"):
            k.pop(f, None)
        with tempfile.TemporaryDirectory() as tmp:
            cand = pathlib.Path(tmp)
            (cand / "knowledge.yaml").write_text(
                yaml.safe_dump(k, allow_unicode=True), encoding="utf-8")
            (cand / "manifest.yaml").write_text(
                (PACKS / "urqmd" / "manifest.yaml").read_text(encoding="utf-8"), encoding="utf-8")
            (cand / "extractors.py").write_text(
                (PACKS / "urqmd" / "extractors.py").read_text(encoding="utf-8"), encoding="utf-8")
            r = pack_score.score_pack(cand, "urqmd")
        self.assertEqual(r["dimensions"]["completeness"], 0.0)
        self.assertLess(r["aggregate"], identity)


if __name__ == "__main__":
    unittest.main()
