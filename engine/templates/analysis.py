#!/usr/bin/env python3
"""Public analysis entry for a generated skill.

Delegates to `analyze_outputs.py`, which summarizes discovered output files.
"""
from pathlib import Path
import runpy
import sys


def main() -> int:
    helper = Path(__file__).resolve().parent / "analyze_outputs.py"
    if not helper.exists():
        print("analyze_outputs.py is missing from this generated skill.", file=sys.stderr)
        return 2
    sys.argv = [str(helper), *sys.argv[1:]]
    runpy.run_path(str(helper), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
