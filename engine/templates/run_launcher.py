#!/usr/bin/env python3
"""Generic tiered run launcher (T0/T1/T2). Model-agnostic: driven by a
run_profile.json (data) and an optional extractors.py (fixed ``extract`` signature).

Best-effort to the deepest tier the environment allows; records which tier was
reached and any blockers. Never silently claims success.
"""
import argparse
import importlib.util
import json
import re
import shutil
import string
import subprocess
import time
from pathlib import Path


_SKIP_DIRS = {".git", "__pycache__", "build", "dist", ".venv", "venv", "node_modules"}


def _looks_like_project(d):
    """Generic, model-agnostic test for 'this dir is an independent project root':
    a VCS checkout (``.git``), or a README plus at least one runnable entry inside.
    Mirrors the scanner's predicate so launcher and scanner agree on the root."""
    d = Path(d)
    if (d / ".git").is_dir():
        return True
    if not (any(d.glob("README*")) or any(d.glob("readme*"))):
        return False
    for p in d.rglob("*.py"):
        if any(part in _SKIP_DIRS for part in p.relative_to(d).parts[:-1]):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "sys.argv[" in text or "parse_args(" in text or "parse_known_args(" in text:
            return True
    return False


class _AmbiguousProjectRoot(Exception):
    """Raised when --project-root is a multi-project workspace: several independent
    project-like children and no single real root to choose."""

    def __init__(self, root, candidates):
        names = ", ".join(sorted(c.name for c in candidates))
        super().__init__(
            f"{root} looks like a multi-project workspace, not a single project "
            f"(independent project roots found: {names}). "
            f"Point --project-root at one of them.")


def _effective_root(root, max_depth=3):
    """Descend to the real project root, the same way the scanner does:
    (1) a *pure wrapper* (exactly one subdir, no files of its own) is descended
        into; (2) a non-project dir with exactly one project-like child is descended
        into (handles a messy parent holding one checkout plus loose files/tooling).
    If the dir is itself a project root, stop. Multiple project-like children ->
    ambiguous workspace -> raise ``_AmbiguousProjectRoot``."""
    root = Path(root)
    for _ in range(max_depth):
        if _looks_like_project(root):
            return root
        children = [c for c in root.iterdir() if c.name not in _SKIP_DIRS]
        dirs = [c for c in children if c.is_dir()]
        files = [c for c in children if c.is_file()]
        if len(dirs) == 1 and not files:
            root = dirs[0]
            continue
        proj_children = [d for d in dirs if _looks_like_project(d)]
        if len(proj_children) == 1:
            root = proj_children[0]
            continue
        if len(proj_children) >= 2:
            raise _AmbiguousProjectRoot(root, proj_children)
        return root
    return root


def _need_ok(root, need):
    """Best-effort, generic interpretation of a run_profile `needs` entry.
    Returns True/False, or None when the need is not something we can check."""
    root = Path(root)
    if need.startswith("build:"):
        return (root / need[len("build:"):] / "build").is_dir()
    if need == "opencl":
        return importlib.util.find_spec("pyopencl") is not None or shutil.which("clinfo") is not None
    return None


def _environment_report(root, needs):
    """T0 environment check: generic tools (via the sibling verify_environment.py)
    plus each declared need. Model-agnostic."""
    env = {"root_exists": Path(root).is_dir(), "tools": {}, "needs": {}}
    verify = Path(__file__).resolve().parent / "verify_environment.py"
    if verify.exists():
        try:
            spec = importlib.util.spec_from_file_location("verify_environment", verify)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            base = mod.check_environment(root)
            env["root_exists"] = base.get("root_exists", env["root_exists"])
            env["tools"] = base.get("tools", {})
        except Exception as exc:
            env["error"] = "verify_environment failed: %s" % exc
    for need in needs or []:
        env["needs"][need] = _need_ok(root, need)
    return env


def _apply_edits(text, edits, output_key, output_value):
    edits = dict(edits or {})
    if output_key:
        edits[output_key] = output_value
    for key, value in edits.items():
        pattern = re.compile(r"(?m)^(\s*" + re.escape(key) + r"\s*=).*$")
        if pattern.search(text):
            # replacement via a function so the value is literal -- a str
            # replacement would interpret \1, \g<>, \n, \t etc. in the value
            # (e.g. a Windows path or any value containing a backslash)
            text = pattern.sub(lambda m, v=value: m.group(1) + " " + str(v), text)
        else:
            text += f"\n{key} = {value}\n"
    return text


def _find(run_root, name, newer_than=None):
    """First non-empty file named ``name`` under ``run_root``. When
    ``newer_than`` is given, skip files older than it -- a stale output from a
    previous run (or a pre-existing file in the source tree) must not be
    mistaken for output this run produced."""
    for p in Path(run_root).rglob(name):
        if not (p.is_file() and p.stat().st_size > 0):
            continue
        if newer_than is not None and p.stat().st_mtime < newer_than:
            continue
        return p
    return None


def _load_extractors(path):
    spec = importlib.util.spec_from_file_location("pack_extractors", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def _subst(token, ctx):
    """Substitute {name} placeholders from ctx; unknown names are left intact."""
    try:
        return string.Formatter().vformat(str(token), (), _SafeDict(ctx))
    except (ValueError, IndexError):
        return str(token)


def _resolve_inputs(decl, cli_inputs):
    """Declared external-input roots: dict name->default(or null) or list of names,
    overridden by ``--input name=path``. Returns {name: value-or-None}. The data
    LOCATION is never derived from source -- it is the user's/pack's to declare."""
    result = {}
    if isinstance(decl, dict):
        result.update(decl)
    elif isinstance(decl, list):
        for k in decl:
            result[k] = None
    for kv in cli_inputs or []:
        if "=" in kv:
            k, v = kv.split("=", 1)
            result[k] = v
    return result


def _run_step(cmds, cwd, ctx, log, label, report):
    """Run a list of commands (string -> shell; list -> argv) in cwd with
    {placeholder} substitution. Non-zero exit -> blocker. Returns ok bool.

    Trust boundary: string-form steps run via the shell after substitution, so
    their text AND the substituted values (pack params, and user --set/--input)
    are trusted. Build/prepare steps come from the pack (author-controlled) and
    this is a locally-run dev tool, so this is acceptable; do NOT feed untrusted
    input here. Use list-form (argv, shell=False) when a value could be hostile."""
    Path(cwd).mkdir(parents=True, exist_ok=True)
    for cmd in cmds or []:
        if isinstance(cmd, list):
            run_arg = [_subst(t, ctx) for t in cmd]
            shell = False
            disp = " ".join(run_arg)
        else:
            run_arg = _subst(cmd, ctx)
            shell = True
            disp = run_arg
        try:
            with open(log, "a") as fh:
                fh.write(f"\n$ [{label}] {disp}\n")
                proc = subprocess.run(run_arg, cwd=str(cwd), shell=shell,
                                      stdout=fh, stderr=subprocess.STDOUT, timeout=3600)
            if proc.returncode != 0:
                report["blockers"].append(f"{label} step failed (exit {proc.returncode}): {disp}")
                return False
        except Exception as exc:
            report["blockers"].append(f"{label} step failed: {exc} ({disp})")
            return False
    return True


def _write_verified_run(report, run_profile_path):
    """固化: record a known-good run into the generated skill's references/.
    Skill dir = run_profile's grandparent (<skill>/scripts/run_profile.json).
    No-op unless a tier >= 1 was reached and the skill's references/ exists."""
    if report.get("tier_reached", 0) < 1:
        return
    refs = Path(run_profile_path).resolve().parents[1] / "references"
    if not refs.is_dir():
        return
    import datetime
    path = refs / "verified-runs.md"
    prefix = "# Verified Runs\n\n" if not path.exists() else ""
    md = [
        f"- date: {datetime.date.today().isoformat()}",
        f"- tier reached: **T{report['tier_reached']}**",
        f"- known-good command: `{report.get('resolved_command')}`",
        "",
    ]
    with path.open("a", encoding="utf-8") as fh:
        fh.write(prefix + "\n".join(md))


def _write_blocked_run(report, run_profile_path):
    if not report.get("blockers"):
        return
    refs = Path(run_profile_path).resolve().parents[1] / "references"
    if not refs.is_dir():
        return
    import datetime
    path = refs / "blocked-runs.md"
    prefix = "# Blocked Runs\n\n" if not path.exists() else ""
    md = [
        f"- date: {datetime.date.today().isoformat()}",
        f"- tier reached: **T{report.get('tier_reached', 0)}**",
        f"- resolved command: `{report.get('resolved_command')}`",
        f"- blockers: {report.get('blockers')}",
        "",
    ]
    with path.open("a", encoding="utf-8") as fh:
        fh.write(prefix + "\n".join(md))


def _write(report, work, run_profile=None):
    if run_profile:
        _write_verified_run(report, run_profile)
        _write_blocked_run(report, run_profile)
    work = Path(work)
    (work / "verification-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    env = report.get("environment") or {}
    missing_tools = [t for t, ok in (env.get("tools") or {}).items() if not ok]
    missing_needs = [n for n, ok in (env.get("needs") or {}).items() if ok is False]
    md = [
        "# Verification Report", "",
        f"- tier reached: **T{report['tier_reached']}**",
        f"- resolved command: `{report['resolved_command']}`",
        f"- environment: root_exists={env.get('root_exists')}, "
        f"missing tools={missing_tools or 'none'}, missing needs={missing_needs or 'none'}",
        f"- tier1 output: `{report['tier1_output']}`",
        f"- observable: `{report['observable']}`",
        f"- plot: `{report['plot']}`",
        f"- blockers: {report['blockers'] or 'none'}", "",
    ]
    (work / "verification-report.md").write_text("\n".join(md), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--run-profile", required=True)
    ap.add_argument("--extractors", default=None)
    ap.add_argument("--cent", default="0_5")
    ap.add_argument("--gpu", default="0")
    ap.add_argument("--input", action="append", default=[],
                    help="declared external-input root: name=path (repeatable)")
    ap.add_argument("--set", action="append", default=[],
                    help="override a run param used in placeholders: name=value (repeatable)")
    ap.add_argument("--max-tier", type=int, default=2)
    args = ap.parse_args()

    try:
        root = _effective_root(Path(args.project_root).resolve())
    except _AmbiguousProjectRoot as exc:
        import sys
        print(f"error: {exc}", file=sys.stderr)
        return 2
    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    profile = json.loads(Path(args.run_profile).read_text(encoding="utf-8"))
    report = {"tier_reached": 0, "blockers": [], "resolved_command": None,
              "tier1_output": None, "observable": None, "plot": None, "environment": None}

    # --- T0: verify environment, edit config, resolve command (no execution) ---
    report["environment"] = _environment_report(root, profile.get("needs"))
    command_argv = profile.get("command_argv")
    if not command_argv:
        report["blockers"].append("run_profile missing command_argv")
        _write(report, work, args.run_profile)
        return 0
    out_root = work / "out"
    base_config = profile.get("base_config")
    edited_cfg = None
    if base_config:
        base_config = str(base_config).replace("<PROJECT_ROOT>", str(root))
        base = root / base_config if not Path(base_config).is_absolute() else Path(base_config)
        if not base.exists():
            report["blockers"].append(f"base_config missing: {base}")
            _write(report, work, args.run_profile)
            return 0
        cfg_text = base.read_text(encoding="utf-8")
        cfg_text = _apply_edits(cfg_text, profile.get("config_edits"),
                                profile.get("output_key"), str(out_root))
        edited_cfg = work / Path(base_config).name
        edited_cfg.write_text(cfg_text, encoding="utf-8")
    elif any("{config}" in str(tok) for tok in command_argv):
        report["blockers"].append("run_profile command_argv uses {config} but base_config is missing")
        _write(report, work, args.run_profile)
        return 0
    # Placeholder context for build/prepare/run: generic names + pack params +
    # declared inputs. The run COMMAND is still pack/engine-derived; this only
    # fills declared slots. Input LOCATIONS come from the user/pack, never source.
    inputs = _resolve_inputs(profile.get("inputs"), args.input)
    ctx = {"root": str(root), "work": str(work), "config": str(edited_cfg or ""),
           "cent": args.cent, "gpu": args.gpu}
    ctx.update({k: str(v) for k, v in (profile.get("params") or {}).items()})
    ctx.update({k: v for k, v in inputs.items() if v is not None})
    for kv in args.set or []:
        if "=" in kv:
            k, v = kv.split("=", 1)
            ctx[k] = v

    # A required input is one that is referenced as {name} but has no value.
    all_cmd_text = " ".join(
        [" ".join(map(str, command_argv))]
        + [" ".join(c) if isinstance(c, list) else str(c)
           for c in (profile.get("build") or []) + (profile.get("prepare") or [])])
    for name, val in inputs.items():
        if val is None and ("{%s}" % name) in all_cmd_text:
            report["blockers"].append(
                f"required input '{name}' not provided (pass --input {name}=/path)")
    argv = [_subst(str(tok).replace("<PROJECT_ROOT>", str(root)), ctx) for tok in command_argv]
    report["resolved_command"] = " ".join(argv)
    report["tier_reached"] = 0
    if report["blockers"]:                     # missing required inputs -> stop at T0
        _write(report, work, args.run_profile)
        return 0
    if args.max_tier < 1:
        _write(report, work, args.run_profile)
        return 0

    # --- T1: build -> prepare -> run -> check tier1_output ---
    log = work / "run.log"
    log.write_text("", encoding="utf-8")
    if profile.get("build"):
        build_dir = root / profile.get("build_dir", ".")
        if not _run_step(profile["build"], build_dir, ctx, log, "build", report):
            _write(report, work, args.run_profile)
            return 0
    if profile.get("run_in") == "work":
        cwd = work / "run"
        cwd.mkdir(parents=True, exist_ok=True)
    else:
        cwd = root / profile.get("work_subdir", ".")
    if profile.get("prepare"):
        if not _run_step(profile["prepare"], cwd, ctx, log, "prepare", report):
            _write(report, work, args.run_profile)
            return 0
    run_start = time.time()
    run_failed = False
    try:
        with open(log, "a") as fh:
            fh.write("\n$ [run] " + " ".join(argv) + "\n")
            proc = subprocess.run(argv, cwd=str(cwd),
                                  stdout=fh, stderr=subprocess.STDOUT, timeout=3600)
        if proc.returncode != 0:
            report["blockers"].append(f"run exited {proc.returncode}; see {log}")
            run_failed = True
    except Exception as exc:
        report["blockers"].append(f"run failed: {exc}")
        run_failed = True
    if run_failed:                              # hard stop: a failed run never reaches T1,
        _write(report, work, args.run_profile)  # so it is never recorded as a known-good run
        return 0
    # only count an output this run actually produced (mtime >= run start, with a
    # small tolerance for coarse filesystem mtime granularity)
    fresh = run_start - 2.0
    t1 = _find(out_root, profile["tier1_output"], fresh) \
        or _find(cwd, profile["tier1_output"], fresh)
    if t1 is None:
        report["blockers"].append(f"tier1 output {profile['tier1_output']} missing/empty "
                                  f"(or stale -- not produced by this run)")
        _write(report, work, args.run_profile)
        return 0
    report["tier1_output"] = str(t1)
    report["tier_reached"] = 1
    if args.max_tier < 2:
        _write(report, work, args.run_profile)
        return 0

    # --- T2: extract one observable ---
    obs = profile.get("tier2_observable")
    if not (obs and args.extractors and Path(args.extractors).exists()):
        report["blockers"].append("no extractors or tier2_observable; stopped at T1")
        _write(report, work, args.run_profile)
        return 0
    try:
        ex = _load_extractors(args.extractors)
        result = ex.extract(obs, str(t1.parent), str(work / "analysis"))
        report["observable"] = result
        # extractors signal graceful failure by returning {"error": ...} rather
        # than raising; that is NOT a reached tier (mirrors the T1 hard stop).
        if isinstance(result, dict) and "error" not in result:
            report["plot"] = result.get("plot")
            report["tier_reached"] = 2
        else:
            err = result.get("error") if isinstance(result, dict) else "extractor returned non-dict"
            report["blockers"].append(f"extract produced no usable observable: {err}")
    except Exception as exc:
        report["blockers"].append(f"extract failed: {exc}")
    _write(report, work, args.run_profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
