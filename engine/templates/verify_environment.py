#!/usr/bin/env python3
"""Generic environment check shipped into a generated skill (model-agnostic)."""
import argparse
import json
import shutil
from pathlib import Path


def check_environment(root) -> dict:
    """Generic, model-agnostic environment check. Reused by the tiered launcher's
    T0 so the same logic backs both the standalone script and the run report."""
    root = Path(root)
    return {
        "root_exists": root.is_dir(),
        "tools": {t: shutil.which(t) is not None for t in ("python3", "cmake", "make", "git")},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    checks = check_environment(args.project_root)
    print(json.dumps(checks, indent=2) if args.json else checks)
    return 0 if checks["root_exists"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
