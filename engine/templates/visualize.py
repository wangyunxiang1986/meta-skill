#!/usr/bin/env python3
"""Create a simple diagnostic report from analysis summary output.

This intentionally has no mandatory plotting dependency. Pack-specific extractors may
produce figures; this generic visualizer gives every generated skill a stable
diagnostic entry point.
"""
import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", required=True, help="Path to analysis summary.json")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    summary_path = Path(args.summary)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    outputs = data.get("outputs", [])
    lines = ["# Output Diagnostics", ""]
    lines.append(f"- run_dir: `{data.get('run_dir', '')}`")
    lines.append(f"- files: {len(outputs)}")
    for item in outputs[:30]:
        lines.append(
            f"- `{item.get('file')}`: rows={item.get('rows')}, "
            f"columns={item.get('columns')}, bytes={item.get('bytes')}"
        )
    report = out / "diagnostics.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("diagnostics written to", report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
