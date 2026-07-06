#!/usr/bin/env python3
"""Non-circular verification of a generated extractor against a column truth.

The circularity trap: if a golden's expected values were reasoned by the same model
that wrote the parser, a column mis-read corrupts BOTH and the golden still passes
(the URQMD py-as-phi / pz-as-eta bug: "T2 passed", physics wrong). Here the check is
grounded in an INDEPENDENT column->field order recovered by drafting.columns (from the
compiler-read `<<` chain or the file's own header), not in the model's reading.

Method -- a discriminating probe:
  * build one probe record where every column holds a DISTINCT, recognisable number
    (col k -> value V_k). Distinct values mean a mis-read column changes the result,
    unlike an all-zeros row that would hide it.
  * from the column truth + a physics map (which field is px/py/pz/charge/...),
    compute the EXPECTED observable INDEPENDENTLY of the extractor.
  * run the candidate extractor on the probe and compare. Mismatch -> reject.

A physics map is the one human/LLM input; but it maps FIELD NAMES ('P[1]'->'px'), not
column numbers -- the order is fixed by the code, so a wrong-column extractor is caught
even with a correct physics map.
"""
import importlib.util
import math
import os
import tempfile


def _probe_values(n):
    """Distinct, non-degenerate probe value per column: 2, 3, 5, 7, ... (primes-ish so
    sums/products are unambiguous). Avoids 0/1 which hide mis-reads."""
    base = [2.0, 3.0, 5.0, 7.0, 11.0, 13.0, 17.0, 19.0, 23.0, 29.0, 31.0, 37.0]
    return [base[i % len(base)] + (i // len(base)) for i in range(n)]


def build_probe_row(fields, sep=" "):
    vals = _probe_values(len(fields))
    return sep.join(("%g" % v) for v in vals), {f: vals[i] for i, f in enumerate(fields)}


def expected_pt(field_value, physics_map):
    """Independent pT from the probe: sqrt(px^2 + py^2) using the TRUTH column values."""
    inv = {v: k for k, v in physics_map.items()}   # physics name -> field token
    px = field_value[inv["px"]]
    py = field_value[inv["py"]]
    return math.sqrt(px * px + py * py)


def expected_eta(field_value, physics_map):
    inv = {v: k for k, v in physics_map.items()}
    px, py, pz = (field_value[inv["px"]], field_value[inv["py"]], field_value[inv["pz"]])
    p = math.sqrt(px * px + py * py + pz * pz)
    if p <= abs(pz) or p == 0:
        return math.copysign(20.0, pz)
    return 0.5 * math.log((p + pz) / (p - pz))


_EXPECT = {"pt": expected_pt, "pt_max": expected_pt, "pt_mean": expected_pt,
           "eta": expected_eta, "eta_max": expected_eta}


def _load(path, name="cand_ext"):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def verify(extractor_path, fields, physics_map, observable, out_filename,
           value_key, header=""):
    """Return {'ok': bool, 'expected': x, 'got': y, 'reason': ...}. A discriminating
    probe row is written to out_filename; the extractor runs on it and its value_key
    result is compared to the truth-derived expectation."""
    if value_key not in _EXPECT:
        return {"ok": None, "reason": "no independent expectation for '%s'" % value_key}
    row, field_value = build_probe_row(fields)
    want = _EXPECT[value_key](field_value, physics_map)
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, out_filename)
        with open(p, "w") as fh:
            if header:
                fh.write(header.rstrip("\n") + "\n")
            fh.write("# event 0 1\n")               # a generic 1-particle event header
            fh.write(row + "\n")
        try:
            ex = _load(extractor_path)
            res = ex.extract(observable, tmp, os.path.join(tmp, "an"))
        except Exception as exc:
            return {"ok": False, "reason": "extractor raised: %s" % exc}
        if not isinstance(res, dict) or "error" in res:
            return {"ok": False, "reason": "extractor error: %s" % (res.get("error") if isinstance(res, dict) else res)}
        got = (res.get("values") or {}).get(value_key)
        if got is None:
            return {"ok": False, "reason": "extractor did not return '%s'" % value_key}
        ok = abs(got - want) <= 1e-6 * max(1.0, abs(want))
        return {"ok": ok, "expected": want, "got": got,
                "reason": "match" if ok else "MISMATCH: column mis-read?"}
