#!/usr/bin/env python3
"""Validate a config file against param_constraints.json (model-agnostic).

Data-driven only: it knows nothing about any specific model — it reads the
constraints emitted by the meta-skill and checks a config's values against them.
"""
import argparse
import configparser
import json
import re
import sys
from pathlib import Path


def _strip_inline_comment(v):
    # Config files commonly use ';' or '#' inline comments; a comment must be
    # preceded by whitespace so values like 'a#b' are left intact.
    return re.split(r"\s[;#]", v, maxsplit=1)[0].strip()


def _parse_config(text):
    vals = {}
    cp = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
    try:
        cp.read_string(text)
        for sec in cp.sections():
            for k, v in cp.items(sec):
                vals[k] = _strip_inline_comment(v)
    except configparser.Error:
        pass
    for m in re.finditer(r"^\s*([A-Za-z_]\w*)\s*[=:]\s*(.+?)\s*$", text, re.M):
        vals.setdefault(m.group(1), _strip_inline_comment(m.group(2)))
    return vals


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def validate(config_text, constraints):
    """Return a sorted list of human-readable violation strings (empty = clean)."""
    violations = set()
    vals = _parse_config(config_text)
    for name, c in constraints.items():
        if name not in vals:
            continue
        v = vals[name]
        if c.get("choices") and v not in [str(x) for x in c["choices"]]:
            violations.add(f"{name}={v}: not in choices {c['choices']}")
        rng = c.get("range")
        nv = _num(v)
        if (isinstance(rng, (list, tuple)) and len(rng) == 2
                and nv is not None and not (rng[0] <= nv <= rng[1])):
            violations.add(f"{name}={v}: out of range {rng[0]}..{rng[1]}")
        for other in c.get("exclusive_with", []) or []:
            if other in vals:
                a, b = sorted((name, other))
                violations.add(f"{a} and {b} are mutually exclusive but both set")
    return sorted(violations)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--constraints", required=True)
    args = ap.parse_args()
    constraints = json.loads(Path(args.constraints).read_text(encoding="utf-8"))
    violations = validate(Path(args.config).read_text(encoding="utf-8"), constraints)
    if violations:
        print("config validation FAILED:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print("config OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
