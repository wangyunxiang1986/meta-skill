#!/usr/bin/env python3
"""Confirmation gate for a generated skill.

A human MUST review the generated skill -- `references/project-understanding.md`,
`references/run-modes.md`, and the latest `verification-report.md` -- and confirm
three things before the skill is used for real work:

  * parameter_meanings -- the parameters mean what the skill says they mean;
  * run_flow           -- the derived run command / flow is correct;
  * observable         -- the extracted observable is the one that matters.

This is a real gate: ``run.py`` refuses to run while it is unconfirmed, and every
``verification-report.md`` is stamped with the confirmation status. The record
lives in ``references/confirmation.yaml`` as a flat ``key: value`` file, parsed
with the standard library only so the gate carries no third-party dependency.
"""
import argparse
import datetime
import sys
from pathlib import Path

_ITEMS = ("parameter_meanings", "run_flow", "observable")


def _confirmation_path(skill_dir):
    return Path(skill_dir) / "references" / "confirmation.yaml"


def read_confirmation(skill_dir):
    """Parse the flat gate file into a dict; ``{}`` when the file is absent."""
    path = _confirmation_path(skill_dir)
    if not path.exists():
        return {}
    data = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, val = line.split(":", 1)
        data[key.strip()] = val.strip()
    return data


def is_confirmed(data):
    """True only when all three items are 'yes' and a confirmer is named."""
    if not data or not data.get("confirmed_by"):
        return False
    return all(str(data.get(item, "")).lower() == "yes" for item in _ITEMS)


def status_line(data):
    if not data:
        return "MISSING (no confirmation.yaml)"
    if is_confirmed(data):
        return f"CONFIRMED by {data.get('confirmed_by')} on {data.get('date') or '?'}"
    reasons = []
    pending = [i for i in _ITEMS if str(data.get(i, "")).lower() != "yes"]
    if pending:
        reasons.append(", ".join(pending) + " not yes")
    if not data.get("confirmed_by"):
        reasons.append("confirmed_by empty")
    return "UNCONFIRMED (" + "; ".join(reasons) + ")"


def write_confirmation(skill_dir, by, note=None):
    """Record a full confirmation (all items yes, who, and when)."""
    path = _confirmation_path(skill_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Confirmation gate -- recorded by scripts/confirm.py.",
        "# Each item was confirmed against the real run by the named human.",
    ]
    lines += [f"{item}: yes" for item in _ITEMS]
    lines.append(f"confirmed_by: {by}")
    lines.append(f"date: {datetime.date.today().isoformat()}")
    if note:
        lines.append(f"note: {note}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Confirmation gate for this generated skill.")
    ap.add_argument("--skill-dir",
                    default=str(Path(__file__).resolve().parent.parent),
                    help="root of the generated skill (default: this script's skill)")
    ap.add_argument("--confirm", action="store_true",
                    help="record confirmation for all items (requires --by)")
    ap.add_argument("--by", help="name of the human confirming")
    ap.add_argument("--note", help="optional free-text note to store")
    ap.add_argument("--status", action="store_true",
                    help="print gate status (default action)")
    args = ap.parse_args(argv)
    skill_dir = Path(args.skill_dir)

    if args.confirm:
        if not args.by:
            print('error: --confirm requires --by "Your Name"', file=sys.stderr)
            return 2
        path = write_confirmation(skill_dir, args.by, args.note)
        print(f"confirmed; wrote {path}")
        return 0

    data = read_confirmation(skill_dir)
    print(status_line(data))
    return 0 if is_confirmed(data) else 3


if __name__ == "__main__":
    raise SystemExit(main())
