#!/usr/bin/env python3
"""Grounding tools for pack drafting (P1).

The rule that prevents a mis-parse like the URQMD column bug (py read as phi, pz as
eta -- "T2 passed" but the physics was wrong): the observable layer (output_meaning,
observable_locator, the extractor and its golden) MUST be derived from the REAL output
of a T1 run and the actual writer code, never from imagination. These helpers surface
that ground truth for a drafter (LLM or human):

  capture_sample        the real head of a tier-1 output file + its column count
  locate_writer         where/how the source writes that file (reveals column ORDER)
  observable_grounding  a brief combining both + the gaps a pack must fill

Anti-circularity: a golden's EXPECTED values must come from independent reasoning about
the sample (physics: "these two partons share eta -> they pile -> peak = ..."), NOT from
whatever the possibly-buggy extractor returns -- else the golden enshrines the bug rather
than catching it. capture_sample gives the format; the expected values are the drafter's
to reason out and A1's golden meta-test then checks them.
"""
import argparse
import json
import sys
from pathlib import Path

from engine import scan as _scan

# hints that a line CARRIES the data fields (so it reveals the column order); plain
# ofstream/open declarations are excluded -- they name the file (-> named_at) but do
# not show columns.
_COLUMN_HINTS = ("savetxt", "create_dataset", "to_csv", "to_hdf", "tofile",
                 "np.save", "fprintf", "fwrite")
_SRC_EXT = {".py", ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".f", ".f90", ".cu"}


def _floatable(tok):
    try:
        float(tok)
        return True
    except ValueError:
        return False


def _is_data_row(line):
    stripped = line.strip()
    if stripped.startswith(("#", "//", "*", "!", ";")):
        return False                              # comment/header, even if it has numbers
    toks = stripped.split()
    if not toks:
        return False
    numeric = sum(1 for t in toks if _floatable(t))
    return numeric >= max(2, len(toks) // 2)


def _find(out_dir, name):
    direct = Path(out_dir) / name
    if direct.is_file():
        return direct
    for f in Path(out_dir).rglob(name):
        if f.is_file():
            return f
    return None


def capture_sample(out_dir, name, max_lines=25):
    """Read the real head of a tier-1 output: separate leading comment/header lines
    from data rows and report the data column count. This is the format ground truth."""
    path = _find(out_dir, name)
    if path is None:
        return {"found": False, "name": name}
    header, data = [], []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            s = line.rstrip("\n")
            if not s.strip():
                continue
            if _is_data_row(s):
                if len(data) < max_lines:
                    data.append(s)
            elif not data and len(header) < 12:
                header.append(s)          # header only counts before any data row
            if len(data) >= max_lines:
                break
    return {
        "found": True,
        "path": str(path),
        "n_columns": len(data[0].split()) if data else 0,
        "header_lines": header,
        "data_head": data,
    }


def _iter_source(root):
    for p in Path(root).rglob("*"):
        if any(part in _scan.SKIP_DIR_NAMES for part in p.parts):
            continue
        if p.is_file() and p.suffix.lower() in _SRC_EXT:
            yield p


def locate_writer(project_root, name, max_hits=10):
    """Find where the source names and writes ``name``. ``field_writes`` are multi-field
    record writes (C++ ``<<`` chains, savetxt, ...) -- they reveal the column ORDER, the
    exact thing a mis-parse gets wrong. Commented-out writes are flagged, not dropped."""
    root = Path(project_root)
    named_at, field_writes = [], []
    for path in _iter_source(root):
        text = _scan.read_text(path)
        if name not in text:                     # only files that write this exact file
            continue
        rel = str(path.relative_to(root))
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if name in line:
                named_at.append({"file": rel, "line": i, "text": stripped[:200]})
            nshift = line.count("<<")
            if nshift >= 3 or any(h in line for h in _COLUMN_HINTS):
                field_writes.append({"file": rel, "line": i,
                                     "commented": stripped.startswith(("//", "#", "*", "!")),
                                     "fields": nshift, "text": stripped[:260]})
    # rank the column-revealing writes: uncommented first, then most fields (a longer
    # << chain / wider row shows more of the column order)
    field_writes.sort(key=lambda h: (not h["commented"], h["fields"]), reverse=True)
    return {"named_at": named_at[:max_hits], "field_writes": field_writes[:max_hits]}


def observable_grounding(project_root, out_dir, tier1_output):
    """Combine the real output sample and the writer code into one grounding record for
    drafting the observable layer of a pack."""
    return {
        "tier1_output": tier1_output,
        "sample": capture_sample(out_dir, tier1_output),
        "writer": locate_writer(project_root, tier1_output),
        "gaps_to_fill": [
            "output_meaning[%s]: describe the columns EXACTLY as the writer emits them" % tier1_output,
            "observable_locator: which file/columns hold each observable",
            "extractors.py: parse those columns; derive physics quantities, do not assume",
            "GOLDEN: a controlled sample with INDEPENDENTLY reasoned expected values (A1)",
        ],
    }


def to_markdown(g):
    s = g["sample"]
    lines = ["# Observable-layer grounding: `%s`" % g["tier1_output"], ""]
    if s.get("found"):
        lines += ["## Real output sample (ground truth for the format)",
                  "- file: `%s`" % s["path"],
                  "- data columns: **%d**" % s["n_columns"], ""]
        if s["header_lines"]:
            lines += ["header/comment lines:", "```"] + s["header_lines"] + ["```", ""]
        lines += ["first data rows:", "```"] + s["data_head"][:8] + ["```", ""]
    else:
        lines += ["## Real output sample", "- NOT FOUND: run to T1 first, then re-run.", ""]
    w = g["writer"]
    lines += ["## Writer in source (reveals the column ORDER)"]
    for h in w["named_at"][:4]:
        lines.append("- named at `%s:%d`: `%s`" % (h["file"], h["line"], h["text"]))
    for h in w["field_writes"][:4]:
        tag = " (commented)" if h["commented"] else ""
        lines.append("- record write `%s:%d`%s: `%s`" % (h["file"], h["line"], tag, h["text"]))
    lines += ["", "## Gaps to fill (grounded in the above, not imagination)"]
    lines += ["- " + g_ for g_ in g["gaps_to_fill"]]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ground the observable layer in real output + writer code.")
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--out-dir", required=True, help="a completed T1 run output dir")
    ap.add_argument("--tier1-output", required=True, help="the tier-1 output filename")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    g = observable_grounding(args.project_root, args.out_dir, args.tier1_output)
    print(json.dumps(g, indent=2, ensure_ascii=False) if args.json else to_markdown(g))
    return 0


if __name__ == "__main__":
    sys.exit(main())
