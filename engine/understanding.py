"""Render a structural project-understanding.md draft (model-agnostic).

The agent enriches the narrative; this module only assembles source-derived
structure plus any meanings supplied by an optional pack.
"""
from typing import Dict, Optional

from engine.generate import md_table, redact_project_path


def render_project_understanding(scan: Dict[str, object], pack: Optional[Dict],
                                 redact_paths: bool = False) -> str:
    knowledge = (pack or {}).get("knowledge", {}) if pack else {}
    name = (pack or {}).get("name", "unknown-project")
    git = scan.get("git", {})
    pmean = knowledge.get("param_meaning", {}) or {}
    omean = knowledge.get("output_meaning", {}) or {}
    project_root = scan.get("project_root")

    def r(value):
        return redact_project_path(value, project_root) if redact_paths else str(value)

    lines = [f"# Project Understanding: {name}", ""]
    lines += ["## Identity", "",
              f"- detected kind: `{name}`",
              f"- git commit: `{git.get('commit', 'unknown')}` "
              f"(describe `{git.get('describe', 'unknown')}`)",
              f"- root: `{r(scan.get('project_root', '?'))}`", ""]

    lines += ["## Directory Summary", ""]
    lines += [f"- `{d}`" for d in scan.get("directories", [])[:60]] or ["- (none)"]
    lines += [""]

    lines += ["## Entry Points", ""]
    for e in scan.get("entrypoints", []):
        lines.append(f"- `{e['path']}`: {e.get('purpose', '')}")
    lines += [""]

    readme_cmds = scan.get("readme_commands", [])
    if readme_cmds:
        lines += ["## Run Commands (from README — authoritative)", ""]
        lines += [f"- `{r(c)}`" for c in readme_cmds]
        lines += [""]

    rows = []
    for p in scan.get("parameters", []):
        meaning = pmean.get(p["name"]) or p.get("help") or ""
        rows.append([f"`{p['name']}`", f"`{r(p.get('default'))}`", meaning,
                     "source-derived" if pmean.get(p["name"]) else "inferred"])
    lines += ["## Parameters", "", md_table(rows, ["Name", "Default", "Meaning", "Origin"]), ""]

    orows = []
    for o in scan.get("output_files", []):
        orows.append([f"`{o['name']}`", omean.get(o["name"], ""),
                      "source-derived" if omean.get(o["name"]) else "inferred"])
    lines += ["## Outputs", "", md_table(orows, ["File", "Meaning", "Origin"]), ""]

    lines += ["## Dependencies", ""]
    lines += [f"- {r(d)}" for d in scan.get("dependencies", [])[:30]] or ["- (none extracted)"]
    lines += [""]

    lines += ["## Source-derived vs Inferred", "",
              "Meanings marked `source-derived` come from the matched knowledge pack; "
              "`inferred` come from code help text or are blank."]
    if not pack:
        lines += ["", "> No knowledge pack matched. This is a STRUCTURAL understanding only. "
                  "Physical/domain meaning needs a pack or human review "
                  "(see the generated skill's `references/model-gaps.md`)."]
    lines += ["", "## Human Review TODO", "",
              "- Physics/engineering goal:", "- Module -> file mapping:",
              "- Parameters needing expert interpretation:",
              "- Outputs needing expert interpretation:", "- Version-specific caveats:", ""]
    return "\n".join(lines)


def main() -> int:
    import argparse
    from pathlib import Path
    from engine import scan as scanmod
    from engine import pack_loader
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--packs-dir", default=str(Path(__file__).resolve().parents[1] / "packs"))
    args = ap.parse_args()
    root = Path(args.project_root)
    try:
        scan = scanmod.scan_project(root)
    except scanmod.AmbiguousProjectRoot as exc:
        import sys
        print(f"error: {exc}", file=sys.stderr)
        return 2
    pack = pack_loader.select_pack(Path(args.packs_dir), scan, root)
    Path(args.out).write_text(render_project_understanding(scan, pack), encoding="utf-8")
    print(f"wrote {args.out} (pack={pack['name'] if pack else 'generic'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
