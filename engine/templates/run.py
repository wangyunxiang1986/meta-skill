#!/usr/bin/env python3
"""Public run entry for a generated skill.

This wrapper keeps the generated skill layout intuitive (`config.py`, `run.py`,
`analysis.py`, `visualize.py`) while delegating tiered execution to
`run_launcher.py` when a knowledge pack supplied a run profile.

It enforces the confirmation gate: this skill will not run for real work until a
human has confirmed it via `scripts/confirm.py`. Pass `--force-unconfirmed` to
override (not recommended). The gate does NOT apply to validation, which invokes
`run_launcher.py` directly to produce the evidence a human reviews before confirming.
"""
from pathlib import Path
import runpy
import sys


def _gate(skill_dir: Path):
    """Return (confirmed: bool, status: str) via the sibling ``confirm.py``."""
    scripts_dir = skill_dir / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        import confirm  # sibling module in scripts/
    except Exception as exc:  # confirm.py missing -> treat as unconfirmed, but say why
        return False, f"gate unavailable ({exc})"
    data = confirm.read_confirmation(skill_dir)
    return confirm.is_confirmed(data), confirm.status_line(data)


def main() -> int:
    scripts_dir = Path(__file__).resolve().parent
    skill_dir = scripts_dir.parent

    argv = sys.argv[1:]
    force = "--force-unconfirmed" in argv
    argv = [a for a in argv if a != "--force-unconfirmed"]

    confirmed, status = _gate(skill_dir)
    if not confirmed and not force:
        print("CONFIRMATION GATE: this skill is not confirmed for use.", file=sys.stderr)
        print(f"  status: {status}", file=sys.stderr)
        print('  confirm: python scripts/confirm.py --confirm --by "Your Name"', file=sys.stderr)
        print("  override: re-run with --force-unconfirmed (not recommended).", file=sys.stderr)
        return 3

    launcher = scripts_dir / "run_launcher.py"
    if not launcher.exists():
        print("run_launcher.py is not available; this generated skill has no runnable run profile.", file=sys.stderr)
        return 2
    sys.argv = [str(launcher), *argv]
    runpy.run_path(str(launcher), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
