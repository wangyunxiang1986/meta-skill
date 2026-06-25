"""Assemble a version-specific skill from a scan + optional knowledge pack.

Model knowledge enters only via ``pack`` (the pack's knowledge dict / extractors).
With ``pack=None`` this still produces a valid, if semantically plain, skill.
"""
from __future__ import annotations

import fnmatch
import json
import re
import shutil
import shlex
import stat
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional

TEMPLATES = Path(__file__).resolve().parent / "templates"


def md_table(rows: List[List[object]], headers: List[str]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines)


def write_file(path: Path, text: str, executable: bool = False) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def redact_project_path(value, project_root):
    """Replace a scanned checkout's absolute root with the portable token used in
    generated references. Non-string values are stringified by callers that render
    Markdown; structured redaction is handled by ``redact_scan_paths``."""
    text = str(value)
    root = str(project_root or "")
    if root and root in text:
        return text.replace(root, "<PROJECT_ROOT>")
    text = re.sub(r"(?<![\w<])/(?:home|Users)/[^/\s`|\"']+",
                  "<LOCAL_PATH>", text)
    text = re.sub(r"(?<![\w<])/(?:tmp|var/tmp)/[^/\s`|\"']+",
                  "<LOCAL_PATH>", text)
    return text


def redact_scan_paths(value, project_root):
    if isinstance(value, dict):
        return {k: redact_scan_paths(v, project_root) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_scan_paths(v, project_root) for v in value]
    if isinstance(value, str):
        return redact_project_path(value, project_root)
    return value


def merge_param_constraints(scan: Dict[str, object], knowledge: Optional[Dict]) -> Dict[str, Dict]:
    """Per-param constraints: scanned structural facts (choices/required/exclusive
    group) merged with pack `param_constraints` (range/exclusive_with/note). Pack
    values win on conflict. Exclusion is normalized to name lists."""
    pack_pc = (knowledge or {}).get("param_constraints", {}) or {}
    groups: Dict[object, List[str]] = {}
    for p in scan.get("parameters", []):
        g = p.get("exclusive_group")
        if g is not None:
            groups.setdefault(g, []).append(p["name"])
    merged: Dict[str, Dict] = {}
    for p in scan.get("parameters", []):
        name = p["name"]
        pc = pack_pc.get(name, {}) or {}
        excl = set(pc.get("exclusive_with", []) or [])
        g = p.get("exclusive_group")
        if g is not None:
            excl.update(n for n in groups.get(g, []) if n != name)
        req = pc["required"] if "required" in pc else p.get("required")
        merged[name] = {
            "choices": pc.get("choices", p.get("choices")),
            "range": pc.get("range"),
            "required": req,
            "exclusive_with": sorted(excl),
            "note": pc.get("note", ""),
        }
    for name, pc in pack_pc.items():           # pack-only params (e.g. INI keys)
        if name not in merged:
            merged[name] = {
                "choices": pc.get("choices"), "range": pc.get("range"),
                "required": pc.get("required"),
                "exclusive_with": sorted(pc.get("exclusive_with", []) or []),
                "note": pc.get("note", ""),
            }
    return merged


def _constraint_cell(c: Dict) -> str:
    if c.get("choices"):
        return "choices: " + ", ".join(str(x) for x in c["choices"])
    rng = c.get("range")
    if isinstance(rng, (list, tuple)) and len(rng) == 2:
        return f"range: {rng[0]}..{rng[1]}"
    return ""


def render_parameters(scan: Dict[str, object], knowledge: Optional[Dict],
                      project_root: Optional[str] = None) -> str:
    meaning_map = (knowledge or {}).get("param_meaning", {}) or {}
    merged = merge_param_constraints(scan, knowledge)
    rows = []
    for p in scan["parameters"]:
        name = p["name"]
        c = merged.get(name, {})
        meaning = meaning_map.get(name) or p.get("help") or ""
        default = redact_project_path(p.get("default"), project_root)
        rows.append([f"`{name}`", p.get("type") or "inferred", f"`{default}`",
                     meaning, _constraint_cell(c),
                     "yes" if c.get("required") else "",
                     ", ".join(c.get("exclusive_with", [])),
                     redact_project_path(p.get("source", ""), project_root)])
    # Pack-supplied parameters: for codes the structural scanner cannot read
    # (e.g. a custom name/value config file), the pack provides the rows directly,
    # each carrying its own `source` provenance.
    seen = {p["name"] for p in scan["parameters"]}
    for pp in (knowledge or {}).get("pack_parameters", []) or []:
        name = pp.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        c = merged.get(name, {})
        cell = _constraint_cell({"choices": pp.get("choices", c.get("choices")),
                                 "range": pp.get("range", c.get("range"))})
        meaning = pp.get("meaning") or meaning_map.get(name) or ""
        rows.append([f"`{name}`", pp.get("type") or "pack", f"`{pp.get('default', '')}`",
                     meaning, cell,
                     "yes" if pp.get("required") else "",
                     ", ".join(pp.get("exclusive_with", []) or []),
                     pp.get("source", "pack")])
    return ("# Parameters\n\n" + md_table(rows,
            ["Name", "Type", "Default", "Meaning", "Choices/Range",
             "Required", "Mutually-exclusive-with", "Source"]) + "\n")


def render_outputs(scan: Dict[str, object], knowledge: Optional[Dict],
                   project_root: Optional[str] = None) -> str:
    meaning_map = (knowledge or {}).get("output_meaning", {}) or {}
    rows = []
    for o in scan["output_files"]:
        meaning = ""
        for pat, m in meaning_map.items():
            if fnmatch.fnmatch(o["name"], pat):
                meaning = m
                break
        rows.append([f"`{o['name']}`", meaning or "(auto-detected output)",
                     f"`{redact_project_path(o['source'], project_root)}`"])
    # Pack-supplied outputs: declared directly when the scanner detected none.
    seen = {o["name"] for o in scan["output_files"]}
    for po in (knowledge or {}).get("pack_outputs", []) or []:
        fname = po.get("file")
        if not fname or fname in seen:
            continue
        seen.add(fname)
        meaning = po.get("meaning") or meaning_map.get(fname) or "(pack-declared output)"
        rows.append([f"`{fname}`", meaning, f"`{po.get('source', 'pack')}`"])
    return "# Outputs\n\n" + md_table(rows, ["File", "Meaning", "Written in"]) + "\n"


def _match_slot(name: str, arg_map: Optional[Dict]) -> Optional[str]:
    low = name.lower()
    for slot, patterns in (arg_map or {}).items():
        for pat in patterns or []:
            if str(pat).lower() in low:
                return slot
    return None


def _readme_command_variants(script_basename: str, readme_commands: Optional[List[str]]) -> List[list]:
    """All README run commands for this script, as token lists [script, arg1, ...]."""
    out = []
    for cmd in readme_commands or []:
        toks = cmd.split()
        for i, tok in enumerate(toks):
            if tok.split("/")[-1] == script_basename:
                out.append(toks[i:])
                break
    return out


def _namelike_count(tokens: list) -> int:
    return sum(1 for a in tokens if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", a))


def _script_for_workdir(entry_path: str, work_subdir: Optional[str]) -> str:
    entry = PurePosixPath(str(entry_path))
    wd = str(work_subdir or ".").strip("/")
    if wd in ("", "."):
        return str(entry)
    wd_path = PurePosixPath(wd)
    try:
        return str(entry.relative_to(wd_path))
    except ValueError:
        return str(entry)


def resolve_command_argv(scan: Dict[str, object], driver: Optional[Dict],
                         work_subdir: Optional[str] = None) -> Optional[list]:
    """Build the launch command. Prefer the README-documented command for the
    primary driver: pair the README usage template (arg NAMES) with a concrete
    README example (real VALUES) -- args that map to a slot become {config}/{cent}/
    {gpu} placeholders, the rest take the README example's real value (e.g. a
    system name). Nothing is hardcoded per version: script, arg names and values
    all come from the README/scan; the pack only supplies arg_map + arg_defaults."""
    entry = scan.get("primary_entry")
    if not entry:
        return None
    fname = entry["path"].split("/")[-1]
    script_token = _script_for_workdir(entry["path"], work_subdir)
    arg_map = (driver or {}).get("arg_map", {})
    defaults = (driver or {}).get("arg_defaults", {})
    code_names = entry.get("argv_names", [])
    code_required = entry.get("argv_required") or len(code_names)

    variants = _readme_command_variants(fname, scan.get("readme_commands", []))
    if variants:
        template = max(variants, key=lambda c: _namelike_count(c[1:]))
        readme_argc = len(template) - 1
        # Cross-check: the launch command must cover every positional arg the code
        # reads. If the README documents fewer than the code requires, the README
        # is stale -> ignore it and reconstruct from the code instead.
        if not (code_required and readme_argc < code_required):
            names = template[1:]
            # a concrete example = same arg count, fewer name-like args (real values)
            examples = [v for v in variants if v is not template and len(v) == len(template)]
            example_vals = min(examples, key=lambda c: _namelike_count(c[1:]))[1:] if examples else []
            argv = list(entry["run_prefix"]) if entry.get("run_prefix") else ["python", script_token]
            for idx, nm in enumerate(names):
                slot = _match_slot(nm, arg_map)
                if slot:
                    argv.append("{%s}" % slot)
                elif idx < len(example_vals):
                    argv.append(example_vals[idx])           # README example's real value
                else:
                    argv.append(str(defaults.get(nm, defaults.get("default", "0"))))
            return argv

    # README absent or too stale -> reconstruct from the code's own positionals.
    argv = list(entry["run_prefix"]) if entry.get("run_prefix") else ["python", script_token]
    names = list(code_names)
    while len(names) < code_required:        # a len() guard implies more args than were named
        names.append("arg%d" % (len(names) + 1))
    for nm in names:
        slot = _match_slot(nm, arg_map)
        val = defaults.get(nm, defaults.get("default"))
        if slot:
            argv.append("{%s}" % slot)
        elif val is not None:
            argv.append(str(val))             # pack-supplied value (named or catch-all)
        else:
            argv.append("<%s>" % nm)          # value is the original code's concern -> user fills
    return argv


def readme_arg_mismatch(scan: Dict[str, object]) -> Optional[Dict[str, int]]:
    """If the README documents fewer positional args for the primary entry than
    the code requires, return both counts (README is stale); else None."""
    entry = scan.get("primary_entry")
    if not entry:
        return None
    fname = entry["path"].split("/")[-1]
    variants = _readme_command_variants(fname, scan.get("readme_commands", []))
    if not variants:
        return None
    template = max(variants, key=lambda c: _namelike_count(c[1:]))
    readme_argc = len(template) - 1
    code_required = entry.get("argv_required") or len(entry.get("argv_names", []))
    if code_required and readme_argc < code_required:
        return {"readme_argc": readme_argc, "code_argc": code_required}
    return None


def readme_status(scan: Dict[str, object]) -> str:
    """missing (no README) / problematic (README present but a problem signal
    fires) / ok. Initial problem signal: a stale documented run command
    (readme_arg_mismatch). Add more signals here later."""
    if not scan.get("readme_path"):
        return "missing"
    if readme_arg_mismatch(scan) is not None:
        return "problematic"
    return "ok"


def readme_source_target(status: str, src_root) -> Path:
    """Where ``--into-source`` writes the generated README. Never returns an
    existing ``README.md``: a fresh ``README.md`` only when one is genuinely
    absent (status missing), otherwise ``README.generated.md`` (covers both a
    stale/problematic README and the race where a README appeared after scan)."""
    src_root = Path(src_root)
    readme = src_root / "README.md"
    if status == "missing" and not readme.exists():
        return readme
    return src_root / "README.generated.md"


def _readme_usage(scan: Dict[str, object], knowledge: Optional[Dict]) -> str:
    profiles = (knowledge or {}).get("run_profiles") or {}
    if profiles:
        minimal = profiles.get("minimal") or next(iter(profiles.values()))
        argv = profile_command_argv(scan, minimal)
        if argv:
            return " ".join(argv)
    if scan.get("primary_entry"):
        argv = resolve_command_argv(scan, None)
        if argv:
            return " ".join(argv)
    return "(no entrypoint detected)"


def _looks_like_dependency(line: str) -> bool:
    """Keep short, tool-name-like dependency entries; drop README prose that the
    coarse scanner picked up (markdown headers, numbered/bulleted install steps,
    sentences, URLs, shell exports). A real dependency is a short token or two,
    not a sentence."""
    s = str(line).strip()
    if not s:
        return False
    if len(s) > 40 or len(s.split()) > 4:        # sentences / long prose
        return False
    if s[0] in "#=*->•":                           # markdown header / bullet
        return False
    if re.match(r"^[(\[]?\d+[.)\]]", s):           # "1.", "(2)", "[3]" numbering
        return False
    if "http://" in s or "https://" in s or "://" in s:
        return False
    if any(tok in s for tok in ("export ", "$", "[", "`", ":")):  # shell / paths / md
        return False
    if ".." in s or "/" in s:                       # command/path fragments (e.g. "cmake ..")
        return False
    return True


def _readme_install(scan: Dict[str, object], knowledge: Optional[Dict]) -> List[str]:
    cmds: List[str] = []
    names = {str(b).split("/")[-1].lower() for b in scan.get("build_files", [])}
    if {"makefile", "gnumakefile"} & names:
        cmds.append("make")
    for t in scan.get("build_targets", []) or []:
        cmds.append(f'cd {t} && mkdir -p build && cd build && cmake .. && make')
    # surface a pack run-profile build step the scanner missed, but skip
    # launcher-internal scratch steps ({work}/{root} placeholders, absolute
    # paths) -- those are not user-facing install instructions.
    profiles = (knowledge or {}).get("run_profiles") or {}
    for prof in profiles.values():
        for step in (prof.get("build") or []):
            step = str(step).strip()
            if not step or step in cmds:
                continue
            if "{" in step or step.startswith("/"):
                continue
            cmds.append(step)
    lines: List[str] = []
    deps: List[str] = []
    for d in scan.get("dependencies", []) or []:    # filter prose + dedupe, keep order
        d = str(d).strip()
        if _looks_like_dependency(d) and d not in deps:
            deps.append(d)
    if deps:
        lines += ["Dependencies:", ""] + [f"- {d}" for d in deps[:20]] + [""]
    if cmds:
        lines += ["Build:", "", "```bash", *cmds, "```"]
    elif not deps:
        lines += ["No build step detected (interpreted/scripted code)."]
    return lines


def _readme_example(scan: Dict[str, object], knowledge: Optional[Dict]) -> List[str]:
    demos = (knowledge or {}).get("demos") or []
    usage = _readme_usage(scan, knowledge)
    if demos:
        d = demos[0]
        argmap = {k: str(v) for k, v in (d.get("args") or {}).items()}
        cmd = " ".join(_fill_token(t, argmap) for t in usage.split())
        return ["```bash", cmd, "```", "", str(d.get("intent", "")).strip()]
    return ["```bash", usage, "```"]


def _readme_description(scan: Dict[str, object], knowledge: Optional[Dict]) -> str:
    desc = (knowledge or {}).get("description")
    if desc:
        return str(desc)
    entry = (scan.get("primary_entry") or {}).get("path")
    if entry:
        return f"Scientific-code package; primary entry `{entry}`."
    return "Scientific-code package."


def render_readme(scan: Dict[str, object], pack: Optional[Dict]) -> str:
    knowledge = (pack or {}).get("knowledge")
    root_name = Path(scan.get("project_root", "project")).name or "project"
    lines = ["<!-- generated by project-explorer-and-skill-creator -->", "",
             f"# {root_name}", "",
             "## Description", "", _readme_description(scan, knowledge), "",
             "## Installation", "", *_readme_install(scan, knowledge), "",
             "## Usage", "", "```bash", _readme_usage(scan, knowledge), "```", "",
             "## Example", "", *_readme_example(scan, knowledge), ""]
    if readme_status(scan) == "problematic":
        mism = readme_arg_mismatch(scan) or {}
        names = " ".join((scan.get("primary_entry") or {}).get("argv_names", []))
        lines += ["## Notes on the existing README", "",
                  f"The existing README documents {mism.get('readme_argc')} positional "
                  f"argument(s) for the primary entry, but the code requires "
                  f"{mism.get('code_argc')} (`{names}`). Use the Usage command above.", ""]
    return "\n".join(lines)


def render_run_modes(scan: Dict[str, object], knowledge: Optional[Dict],
                     project_root: Optional[str] = None) -> str:
    lines = ["# Run Modes", ""]
    readme_cmds = scan.get("readme_commands", [])
    if readme_cmds:
        display_cmds = [redact_project_path(cmd, project_root) for cmd in readme_cmds]
        lines += ["## Run commands (from README)", "", "```bash", *display_cmds, "```", ""]
        mism = readme_arg_mismatch(scan)
        if mism:
            lines += [
                f"> ⚠ README documents {mism['readme_argc']} positional arg(s) but the code "
                f"requires {mism['code_argc']}. The README looks stale; the command below is "
                f"reconstructed from the code — fill any `<...>` placeholders yourself.", ""]
    profiles = (knowledge or {}).get("run_profiles", {}) or {}
    if profiles:
        for name, prof in profiles.items():
            derived = resolve_command_argv(scan, prof["driver"], prof.get("work_subdir")) \
                if prof.get("driver") else None
            argv = profile_command_argv(scan, prof)
            cmd = " ".join(argv) if argv else "(no entrypoint detected by scan)"
            cmd = redact_project_path(cmd, project_root)
            lines += [f"## {name} (entry from scan + pack run-knobs)", "", "```bash", cmd, "```", ""]
            # provenance note when the command is a pack-supplied fallback, not engine-derived
            if argv and not derived and prof.get("command"):
                src = prof.get("command_source", "pack-supplied (derivation fallback)")
                lines += [f"> command source: {src}", ""]
            if prof.get("tier1_output"):
                lines += [f"T1 output: `{prof['tier1_output']}`; "
                          f"T2 observable: `{prof.get('tier2_observable', '-')}`", ""]
    else:
        for e in scan.get("entrypoints", []):
            fname = e["path"].split("/")[-1]
            if e.get("cli_style") == "argv":
                argline = " ".join(f"<{n}>" for n in e.get("argv_names", [])) or "<args...>"
                cmd = f"python {_script_for_workdir(e['path'], '.')} {argline}"
            elif e.get("cli_style") == "argparse":
                cmd = f"python {_script_for_workdir(e['path'], '.')} --help    # see references/parameters.md"
            else:
                continue
            lines += [f"## {fname}", "", "```bash", cmd, "```", ""]
    targets = scan.get("build_targets", [])
    if targets:
        lines += ["## Builds", "", "```bash"]
        for t in targets:
            lines += [f'cd "<PROJECT_ROOT>/{t}" && mkdir -p build && cd build && cmake .. && make']
        lines += ["```", ""]
    return "\n".join(lines)


def _fill_token(tok: str, argmap: Dict[str, str]) -> str:
    try:
        return str(tok).format(**argmap)
    except (KeyError, IndexError, ValueError):
        return str(tok)


def render_demos(scan: Dict[str, object], knowledge: Optional[Dict],
                 project_root: Optional[str] = None) -> str:
    lines = ["# Demos", ""]
    profiles = (knowledge or {}).get("run_profiles", {}) or {}
    base_argv = None
    if profiles:
        prof = profiles.get("minimal") or next(iter(profiles.values()))
        if prof.get("driver"):
            base_argv = resolve_command_argv(scan, prof["driver"], prof.get("work_subdir"))
        elif prof.get("command_template"):
            base_argv = shlex.split(str(prof["command_template"]))
    if base_argv:
        lines += ["## derived baseline", "",
                  "```bash", redact_project_path(" ".join(base_argv), project_root), "```", ""]
    else:
        lines += ["_No runnable command derived (generic skill)._", ""]
    for d in (knowledge or {}).get("demos", []) or []:
        argmap = {"config": "<config>", "cent": "<cent>", "gpu": "<gpu>"}
        argmap.update({k: str(v) for k, v in (d.get("args") or {}).items()})
        cmd = " ".join(_fill_token(t, argmap) for t in base_argv) if base_argv \
            else "(no derived command)"
        cmd = redact_project_path(cmd, project_root)
        lines += [f"## {d.get('title', 'demo')}", "",
                  d.get("intent", ""), "", "```bash", cmd, "```", ""]
    return "\n".join(lines)


def _slug(value: str) -> str:
    text = str(value or "").lower().replace("_", "-").replace("/", "-")
    text = re.sub(r"[^a-z0-9-]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def generated_skill_name(scan: Dict[str, object], pack: Optional[Dict]) -> str:
    base = _slug((pack or {}).get("name", "generated-project-skill")) or "generated-project-skill"
    root_name = _slug(Path(scan.get("project_root", "project")).name) or "project"
    describe = _slug(((scan.get("git") or {}).get("describe") or ""))
    parts = [base, root_name]
    if describe:
        parts.append(describe)
    return "-".join(parts)


def render_skill_md(scan: Dict[str, object], pack: Optional[Dict]) -> str:
    name = generated_skill_name(scan, pack)
    pack_name = (pack or {}).get("name", "generic")
    entry_lines = "\n".join(f"- `{e['path']}`: {e.get('purpose', '')}" for e in scan.get("entrypoints", [])) \
        or "- (none detected)"
    readme_commands = scan.get("readme_commands", [])
    project_root = scan.get("project_root")
    readme_lines = "\n".join(f"- `{redact_project_path(c, project_root)}`" for c in readme_commands) or "- (none detected)"
    intent = ""
    rules = (pack or {}).get("knowledge", {}).get("intent_rules", []) if pack else []
    if rules:
        intent = "\n## Intent Mapping\n\n" + "\n".join(
            f"- {r.get('match')} -> `{r.get('plan')}`" for r in rules) + "\n"
    has_run_profile = bool(((pack or {}).get("knowledge") or {}).get("run_profiles"))
    run_line = "- `scripts/run.py`: public run entry; wraps `run_launcher.py` when a run profile exists."
    if not has_run_profile:
        run_line += " This generic skill has no runnable pack profile yet."
    return (
        f"---\nname: {name}\n"
        f"description: \"Version-specific skill for this scanned checkout.\"\n---\n\n"
        f"# {name}\n\n"
        f"## What This Program Does\n\n"
        f"This skill was generated from one scanned checkout using the `{pack_name}` knowledge "
        f"pack where available. Treat `references/project-profile.json` and "
        f"`references/project-understanding.md` as the version-specific source of truth.\n\n"
        f"## When To Use\n\n"
        f"Use this skill for tasks involving this exact checkout: inspect its parameters, "
        f"prepare configs, run documented workflows, analyze outputs, or reproduce verified "
        f"demos. Do not assume another fork has the same commands or outputs.\n\n"
        f"## Workflow\n\n"
        f"1. Read `references/project-understanding.md` and `references/run-modes.md`.\n"
        f"2. Validate requested parameter edits with `scripts/config.py`.\n"
        f"3. Run through `scripts/run.py` when a run profile is available.\n"
        f"4. Summarize outputs with `scripts/analysis.py` and make diagnostics with "
        f"`scripts/visualize.py`.\n"
        f"5. Record successful runs in `references/verified-runs.md` and blockers in "
        f"`references/blocked-runs.md`.\n\n"
        f"## Entry Points\n\n{entry_lines}\n\n"
        f"## README Run Commands\n\n{readme_lines}\n\n"
        f"## References\n\n"
        f"- `references/project-profile.json`\n"
        f"- `references/project-understanding.md`\n"
        f"- `references/parameters.md`\n"
        f"- `references/outputs.md`\n"
        f"- `references/run-modes.md`\n"
        f"- `references/demos.md`\n"
        f"- `references/verified-runs.md`\n"
        f"- `references/blocked-runs.md`\n"
        f"- `references/model-gaps.md`\n\n"
        f"## Scripts\n\n"
        f"- `scripts/config.py`: validate parameter choices, ranges, and exclusions.\n"
        f"{run_line}\n"
        f"- `scripts/analysis.py`: public analysis entry; wraps output summary helpers.\n"
        f"- `scripts/visualize.py`: create diagnostic plots or text diagnostics.\n"
        f"- `scripts/verify_environment.py`: check generic tools and project root.\n\n"
        f"## Demos\n\n"
        f"Start with `references/demos.md`; prefer demos that also appear in "
        f"`references/verified-runs.md`.\n\n"
        f"## Validation Status\n\n"
        f"Check `references/verified-runs.md` and the latest `verification-report.md` from "
        f"the run directory before claiming the skill works in this environment.\n\n"
        f"## If Blocked\n\n"
        f"Do not report a deeper tier as successful. Record the blocker, inspect "
        f"`references/model-gaps.md`, update the generated scripts or source knowledge pack, "
        f"then re-run validation.\n"
        f"{intent}"
    )


def render_model_gaps(scan: Dict[str, object], pack: Optional[Dict]) -> str:
    if pack:
        return (f"# Model Gaps\n\nPack `{pack['name']}` matched. Record any remaining "
                f"domain caveats a human expert should fill here.\n")
    return ("# Model Gaps\n\nNo knowledge pack matched (generic). This skill carries only "
            "structural facts; physical meanings / intent mapping / observable extraction "
            "need a pack or human input here.\n")


_GENERATED_FILES = [
    "SKILL.md",
    "references/parameters.md",
    "references/outputs.md",
    "references/run-modes.md",
    "references/demos.md",
    "references/model-gaps.md",
    "references/project-profile.json",
    "references/project-understanding.md",
    "references/verified-runs.md",
    "references/blocked-runs.md",
    "references/generated-README.md",
    "scripts/verify_environment.py",
    "scripts/analyze_outputs.py",
    "scripts/config.py",
    "scripts/run.py",
    "scripts/analysis.py",
    "scripts/visualize.py",
    "scripts/param_constraints.json",
    "scripts/extractors.py",
    "scripts/run_profile.json",
    "scripts/run_launcher.py",
]


def clean_generated_files(out_dir: Path) -> None:
    for rel in _GENERATED_FILES:
        path = Path(out_dir) / rel
        if path.exists() and path.is_file():
            path.unlink()


def profile_command_argv(scan: Dict[str, object], profile: Dict[str, object]) -> Optional[list]:
    if profile.get("driver"):
        argv = resolve_command_argv(scan, profile["driver"], profile.get("work_subdir"))
        if argv:
            return argv                       # engine-derived command preferred
    if profile.get("command"):                # pack-supplied fallback (e.g. non-Python
        cmd = profile["command"]              # code the scanner cannot derive a command for)
        return list(cmd) if isinstance(cmd, list) else shlex.split(str(cmd))
    if profile.get("command_argv"):
        return list(profile["command_argv"])
    if profile.get("command_template"):
        return shlex.split(str(profile["command_template"]))
    return None


def generate(scan: Dict[str, object], pack: Optional[Dict], out_dir: Path) -> Dict[str, object]:
    out_dir = Path(out_dir)
    clean_generated_files(out_dir)
    knowledge = (pack or {}).get("knowledge")
    project_root = scan.get("project_root")
    write_file(out_dir / "SKILL.md", render_skill_md(scan, pack))
    write_file(out_dir / "references/parameters.md", render_parameters(scan, knowledge, project_root))
    write_file(out_dir / "references/outputs.md", render_outputs(scan, knowledge, project_root))
    write_file(out_dir / "references/run-modes.md", render_run_modes(scan, knowledge, project_root))
    write_file(out_dir / "references/demos.md", render_demos(scan, knowledge, project_root))
    write_file(out_dir / "references/model-gaps.md", render_model_gaps(scan, pack))
    write_file(out_dir / "references/verified-runs.md", "# Verified Runs\n\n")
    write_file(out_dir / "references/blocked-runs.md", "# Blocked Runs\n\n")
    status = readme_status(scan)
    if status != "ok":
        write_file(out_dir / "references/generated-README.md", render_readme(scan, pack))
    write_file(out_dir / "references/project-profile.json",
               json.dumps(redact_scan_paths(scan, project_root), indent=2))
    from engine import understanding as _understanding
    write_file(out_dir / "references/project-understanding.md",
               _understanding.render_project_understanding(scan, pack, redact_paths=True))
    (out_dir / "scripts").mkdir(parents=True, exist_ok=True)
    for tmpl in ("verify_environment.py", "analyze_outputs.py", "config.py",
                 "run.py", "analysis.py", "visualize.py"):
        src = TEMPLATES / tmpl
        if src.exists():
            shutil.copy(src, out_dir / "scripts" / tmpl)
    import json as _json_pc
    _all_pc = merge_param_constraints(scan, knowledge)
    _actionable = {k: v for k, v in _all_pc.items()
                   if v.get("choices") or v.get("range") or v.get("exclusive_with")}
    write_file(out_dir / "scripts/param_constraints.json",
               _json_pc.dumps(_actionable, indent=2))
    if pack and pack.get("extractors_path"):
        shutil.copy(pack["extractors_path"], out_dir / "scripts" / "extractors.py")
    profiles = ((pack or {}).get("knowledge") or {}).get("run_profiles")
    if profiles:
        import json as _json
        minimal = dict(profiles.get("minimal") or next(iter(profiles.values())))
        argv = profile_command_argv(scan, minimal)
        if argv:
            minimal["command_argv"] = argv   # scan/template-derived; not hardcoded in the engine
        # carry run-knob defaults as placeholder params for the launcher's
        # build/prepare/run substitution (e.g. {jobid}); generic, not model-specific
        arg_defaults = (minimal.get("driver") or {}).get("arg_defaults")
        if arg_defaults and "params" not in minimal:
            minimal["params"] = dict(arg_defaults)
        write_file(out_dir / "scripts/run_profile.json",
                   _json.dumps(redact_scan_paths(minimal, project_root), indent=2))
        launcher = TEMPLATES / "run_launcher.py"
        if launcher.exists():
            shutil.copy(launcher, out_dir / "scripts" / "run_launcher.py")
    return {"name": generated_skill_name(scan, pack), "out_dir": str(out_dir),
            "readme_status": status}


def skill_exists(out_dir: Path) -> bool:
    """True when ``out_dir`` already holds a usable (non-empty) ``SKILL.md``."""
    skill_md = Path(out_dir) / "SKILL.md"
    return skill_md.is_file() and bool(skill_md.read_text(encoding="utf-8").strip())


def compose(scan: Dict[str, object], pack: Optional[Dict], out_dir: Path,
            force: bool = False) -> Dict[str, object]:
    """Compose step: skip generation when a usable skill already exists.

    Mirrors the ``Existing skill?`` decision: if a skill is already present at
    ``out_dir`` and ``force`` is not set, leave it untouched and report that the
    workflow should proceed directly to validation. Otherwise (re)generate it.
    """
    out_dir = Path(out_dir)
    if not force and skill_exists(out_dir):
        return {"name": generated_skill_name(scan, pack), "out_dir": str(out_dir),
                "skipped": True, "reason": "existing skill present"}
    report = generate(scan, pack, out_dir)
    report["skipped"] = False
    return report


def main() -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(description="Generate a version-specific skill")
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--packs-dir", default=str(Path(__file__).resolve().parents[1] / "packs"))
    ap.add_argument("--force", action="store_true",
                    help="regenerate even if a usable skill already exists at --out-dir")
    ap.add_argument("--into-source", action="store_true",
                    help="also write the generated README into the source tree "
                         "(README.md if missing; README.generated.md if the existing "
                         "README is stale; never overwrites an existing README.md)")
    args = ap.parse_args()
    from engine import scan as scanmod
    from engine import pack_loader
    root = Path(args.project_root)
    try:
        scan = scanmod.scan_project(root)
    except scanmod.AmbiguousProjectRoot as exc:
        import sys
        print(f"error: {exc}", file=sys.stderr)
        return 2
    pack = pack_loader.select_pack(Path(args.packs_dir), scan, root)
    report = compose(scan, pack, Path(args.out_dir), force=args.force)
    if args.into_source:
        status = readme_status(scan)
        if status != "ok":
            src_root = Path(scan.get("project_root") or args.project_root)
            target = readme_source_target(status, src_root)
            target.write_text(render_readme(scan, pack), encoding="utf-8")
            report["readme_written_to"] = str(target)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
