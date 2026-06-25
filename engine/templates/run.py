#!/usr/bin/env python3
"""Public run entry for a generated skill.

This wrapper keeps the generated skill layout intuitive (`config.py`, `run.py`,
`analysis.py`, `visualize.py`) while delegating tiered execution to
`run_launcher.py` when a knowledge pack supplied a run profile.
"""
from pathlib import Path
import runpy
import sys


def main() -> int:
    launcher = Path(__file__).resolve().parent / "run_launcher.py"
    if not launcher.exists():
        print("run_launcher.py is not available; this generated skill has no runnable run profile.", file=sys.stderr)
        return 2
    sys.argv = [str(launcher), *sys.argv[1:]]
    runpy.run_path(str(launcher), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
