#!/usr/bin/env python3
"""Pack-generator benchmark (P0): score a CANDIDATE knowledge pack against a
hand-written REFERENCE pack used as ground truth.

Why: the plan is to have an LLM draft `packs/<model>/` by reading a code checkout.
Before trusting that, we need a measuring stick. We already have four human-curated
packs (clvisc, smash, urqmd, lbt); this scores any candidate pack against one of them
so we can tell how close an LLM draft gets -- and it can be built and validated now,
with no LLM in the loop.

The scorer is model-agnostic: it compares two pack directories along fixed dimensions.
The strongest dimension, ``extractor``, is fully objective -- it runs the candidate's
extractor against the reference's checked-in GOLDEN sample (the A1 regression) and
checks the computed values, so a mis-parse scores low no matter how plausible the prose.

Dimensions (each in [0, 1]):
  manifest      match-marker overlap with the reference rule
  params        param_meaning name coverage (+ a soft lexical meaning overlap)
  outputs       output_meaning file + observable_locator coverage
  run_recipe    key run_profile fields agree (tier1/tier2, arg_map slots, build/
                prepare/inputs presence, base_config/work_subdir)
  extractor     candidate extractor reproduces the reference GOLDEN values (objective)
  completeness  presence of description / intent_rules / param_constraints / demos
Aggregate: weighted mean, with extractor + run_recipe weighted highest because they
decide whether the generated skill actually runs and measures the right thing.
"""
import argparse
import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]

WEIGHTS = {
    "extractor": 0.30,
    "run_recipe": 0.25,
    "params": 0.15,
    "outputs": 0.15,
    "completeness": 0.10,
    "manifest": 0.05,
}

_WORD = re.compile(r"[A-Za-z一-鿿]+")


# ------------------------------------------------------------------ loading
def _load_yaml(path):
    path = Path(path)
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _golden_for(reference, tests_dir):
    tf = Path(tests_dir) / ("test_pack_%s_extractors.py" % reference)
    if not tf.exists():
        return None
    mod = _load_module(tf, "golden_%s" % reference)
    return getattr(mod, "GOLDEN", None)


# ------------------------------------------------------------------ helpers
def _coverage(candidate_keys, reference_keys):
    """Recall of the reference's keys: how much of the ground truth is present."""
    ref = set(reference_keys)
    if not ref:
        return 1.0
    return len(ref & set(candidate_keys)) / len(ref)


def _words(text):
    return set(w.lower() for w in _WORD.findall(str(text)) if len(w) > 1)


def _lexical_overlap(cand_meaning, ref_meaning):
    """Soft Jaccard on the words of two meaning strings (a rough 'says the same
    thing' proxy; a real semantic score would need an LLM judge, deferred)."""
    keys = set(ref_meaning) & set(cand_meaning)
    if not keys:
        return 0.0
    total = 0.0
    for k in keys:
        a, b = _words(cand_meaning[k]), _words(ref_meaning[k])
        total += (len(a & b) / len(a | b)) if (a | b) else 0.0
    return total / len(keys)


def _profile(knowledge):
    profs = (knowledge or {}).get("run_profiles") or {}
    return profs.get("minimal") or (next(iter(profs.values())) if profs else {})


def _manifest_markers(manifest):
    out = []
    for cond in ((manifest or {}).get("match") or {}).get("any_of") or []:
        for k in ("file_exists", "readme_contains"):
            if k in cond:
                out.append(str(cond[k]))
    return out


# ------------------------------------------------------------------ dimensions
def _score_manifest(cand_dir, ref_dir):
    cand = _manifest_markers(_load_yaml(Path(cand_dir) / "manifest.yaml"))
    ref = _manifest_markers(_load_yaml(Path(ref_dir) / "manifest.yaml"))
    return _coverage(cand, ref)


def _score_params(cand_k, ref_k):
    cov = _coverage((cand_k.get("param_meaning") or {}),
                    (ref_k.get("param_meaning") or {}))
    lex = _lexical_overlap(cand_k.get("param_meaning") or {},
                           ref_k.get("param_meaning") or {})
    return cov, lex


def _score_outputs(cand_k, ref_k):
    out_cov = _coverage(cand_k.get("output_meaning") or {},
                        ref_k.get("output_meaning") or {})
    obs_cov = _coverage(cand_k.get("observable_locator") or {},
                        ref_k.get("observable_locator") or {})
    return 0.5 * out_cov + 0.5 * obs_cov


def _score_run_recipe(cand_k, ref_k):
    cp, rp = _profile(cand_k), _profile(ref_k)
    if not rp:
        return 1.0
    checks = []
    checks.append(cp.get("tier1_output") == rp.get("tier1_output"))
    checks.append(cp.get("tier2_observable") == rp.get("tier2_observable"))
    # arg_map semantic slots (config/cent/gpu/...) present in candidate
    ref_slots = set(((rp.get("driver") or {}).get("arg_map") or {}))
    cand_slots = set(((cp.get("driver") or {}).get("arg_map") or {}))
    checks.append(_coverage(cand_slots, ref_slots) >= 0.99 if ref_slots else True)
    # a literal command is an alternative to a driver arg_map
    if not ref_slots:
        checks.append(bool(cp.get("command") or cp.get("command_argv")) ==
                      bool(rp.get("command") or rp.get("command_argv")))
    for field in ("build", "prepare"):
        checks.append(bool(cp.get(field)) == bool(rp.get(field)))
    checks.append(set(cp.get("inputs") or {}) >= set(rp.get("inputs") or {})
                  if rp.get("inputs") else True)
    checks.append(bool(cp.get("base_config")) == bool(rp.get("base_config")))
    return sum(1 for c in checks if c) / len(checks)


def _score_extractor(cand_dir, golden):
    """Run the candidate extractor against the reference GOLDEN; fraction of expected
    values reproduced within tolerance. 0 if there is no extractor or it errors."""
    if not golden:
        return None
    ext = Path(cand_dir) / "extractors.py"
    if not ext.exists():
        return 0.0
    try:
        ex = _load_module(ext, "cand_ext_%s" % Path(cand_dir).name)
    except Exception:
        return 0.0
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, content in golden["files"].items():
            f = root / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content, encoding="utf-8")
        try:
            res = ex.extract(golden["observable"], str(root / golden.get("out_subdir", "")),
                             str(root / "_an"))
        except Exception:
            return 0.0
        if not isinstance(res, dict) or "error" in res:
            return 0.0
        vals = res.get("values") or {}
        tol = golden.get("tol", 1e-6)
        exp = golden["expect"]
        ok = sum(1 for k, v in exp.items()
                 if k in vals and abs(vals[k] - v) <= tol)
        return ok / len(exp) if exp else 1.0


def _score_completeness(cand_k):
    fields = [
        bool((cand_k.get("description") or "").strip()) if isinstance(cand_k.get("description"), str) else bool(cand_k.get("description")),
        bool(cand_k.get("intent_rules")),
        bool(cand_k.get("param_constraints")),
        bool(cand_k.get("demos")),
    ]
    return sum(1 for f in fields if f) / len(fields)


# ------------------------------------------------------------------ top level
def score_pack(candidate_dir, reference, packs_dir=None, tests_dir=None):
    packs_dir = Path(packs_dir or (REPO / "packs"))
    tests_dir = Path(tests_dir or (REPO / "tests"))
    ref_dir = packs_dir / reference
    cand_k = _load_yaml(Path(candidate_dir) / "knowledge.yaml")
    ref_k = _load_yaml(ref_dir / "knowledge.yaml")
    golden = _golden_for(reference, tests_dir)

    param_cov, param_lex = _score_params(cand_k, ref_k)
    dims = {
        "manifest": _score_manifest(candidate_dir, ref_dir),
        "params": param_cov,
        "outputs": _score_outputs(cand_k, ref_k),
        "run_recipe": _score_run_recipe(cand_k, ref_k),
        "extractor": _score_extractor(candidate_dir, golden),
        "completeness": _score_completeness(cand_k),
    }
    # aggregate over scored (non-None) dimensions, renormalising weights
    num = den = 0.0
    for name, score in dims.items():
        if score is None:
            continue
        w = WEIGHTS[name]
        num += w * score
        den += w
    aggregate = (num / den) if den else 0.0
    return {
        "candidate": str(candidate_dir),
        "reference": reference,
        "dimensions": dims,
        "soft": {"param_meaning_lexical": round(param_lex, 3)},
        "aggregate": round(aggregate, 4),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Score a candidate pack vs a reference pack.")
    ap.add_argument("--candidate", required=True, help="candidate pack directory")
    ap.add_argument("--reference", required=True, help="reference model name under packs/")
    ap.add_argument("--packs-dir", default=None)
    ap.add_argument("--tests-dir", default=None)
    args = ap.parse_args(argv)
    report = score_pack(args.candidate, args.reference, args.packs_dir, args.tests_dir)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
