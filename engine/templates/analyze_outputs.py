#!/usr/bin/env python3
"""Generic output-shape summary shipped into a generated skill (model-agnostic)."""
import argparse
import json
from pathlib import Path

GLOBS = ["*.dat", "*.txt", "*.csv", "*.h5"]


def shape(path: Path) -> dict:
    rows = cols = 0
    preview = []
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                parts = s.split()
                if cols == 0:
                    cols = len(parts)
                    preview = parts[:8]
                rows += 1
    except Exception:
        pass
    return {"file": path.name, "rows": rows, "columns": cols,
            "bytes": path.stat().st_size, "first_row": preview}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    run = Path(args.run_dir)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for g in GLOBS:
        files.extend(run.rglob(g))
    rows = [shape(p) for p in sorted(set(files)) if p.is_file()]
    (out / "summary.json").write_text(
        json.dumps({"run_dir": str(run), "outputs": rows}, indent=2), encoding="utf-8")
    print("analysis written to", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
