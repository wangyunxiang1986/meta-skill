#!/usr/bin/env python3
"""Auto-candidate demo: build a runnable skill for a checkout using ONLY information
that can be obtained automatically -- the structural scan plus grounding on a real T1
output -- and drive it to T2. No hand-authored physics priors (parameter meanings,
physical ranges, sanity bounds) are used.

The point (the終点 the user cares about): a *usable* skill needs a run recipe + an
observable layer, and both are automatically derivable -- the scan gives the entry, the
run command comes from the tool's own usage, and drafting.ground pulls the observable
names straight out of the real output header. What is NOT auto-derivable (a parameter's
physical meaning, whether the produced number is physically reasonable) is exactly the
part that does NOT decide whether the skill runs -- only whether you can trust the value.

Given a checkout, a run command, and the tier-1 output filename, this:
  1. scans the checkout (structure),
  2. runs the command to T1 and grounds the observable layer on the real output header,
  3. synthesises an auto-candidate pack (command + grounded observable_locator +
     a header-reading extractor) with NO physics priors,
  4. generates the skill and drives it to T2, reporting the tier reached.

The extractor itself is synthesised by drafting.gen_extractor (the single home for
extractor codegen), dispatched on the paradigm drafting.columns recovers: a name-addressed
header_kv reader, a mechanical translation of the '# key = value' header grounding exposes,
not a physics prior.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from drafting import columns, gen_extractor, ground          # noqa: E402


def build_candidate(project_root, command, tier1_output, out_dir, work_root):
    """Assemble an auto-only candidate pack under work_root/pack/auto. Returns a dict
    describing what was auto-derived vs what a prior would add."""
    root = Path(project_root)
    from engine import scan as scanmod
    sc = scanmod.scan_project(root)
    sample = ground.capture_sample(out_dir, tier1_output)
    if not sample.get("found"):
        return {"error": "tier1 output %s not found in %s (run to T1 first)" % (tier1_output, out_dir)}
    # Recognise the output paradigm with the SAME independent parser the packs use
    # (drafting.columns). derive_demo's no-priors story only holds for header_kv
    # (name-addressed) outputs: the observable names come straight out of the
    # '# key = value' header. A columnar (position-addressed) output would need a
    # physics_map prior to name px/py/pz -- the human-confirmation part -- so hand off
    # honestly instead of emitting an empty candidate.
    truth = columns.column_truth(header_kv_lines=sample.get("header_lines", []))
    if truth["paradigm"] != "header_kv":
        return {"error": "auto-derivation (no priors) supports header_kv outputs only; "
                         "'%s' is position-addressed and needs a physics_map prior "
                         "(px/py/pz) -- hand off to a human or use a knowledge pack"
                         % truth["paradigm"],
                "paradigm": truth["paradigm"]}
    observables = truth["fields"]
    pattern = re.escape(tier1_output).replace(r"0", r"\d") if tier1_output[0].isdigit() else re.escape(tier1_output)
    # tier2 observable: prefer a multiplicity-like field if present, else the first
    tier2 = next((o for o in observables if o.lower() in ("mult", "multiplicity", "n", "dnch")), None) \
        or (observables[0] if observables else None)

    pack = Path(work_root) / "pack" / "auto"
    pack.mkdir(parents=True, exist_ok=True)
    (pack / "manifest.yaml").write_text(
        "name: auto\nmatch:\n  any_of:\n    - file_exists: %s\n"
        % ((sc.get("primary_entry") or {}).get("path") or "."), encoding="utf-8")
    locator = "".join("  %s: { file: \"%s\" }\n" % (o, tier1_output) for o in observables)
    # if the command invokes a prebuilt binary (./x), stage it into the work dir first
    # (locating it under the checkout -- itself an automatic step, no prior needed).
    prepare = ["mkdir -p {work}/out"]
    if command and str(command[0]).startswith("./"):
        exe = str(command[0])[2:]
        prepare.append('cp "$(find {root} -name %s -type f | head -1)" .' % exe)
    # emit each prepare step as a YAML single-quoted scalar (the shell strings contain
    # double quotes, so single-quote the YAML and escape any single quotes by doubling).
    prepare_yaml = "".join("      - '%s'\n" % p.replace("'", "''") for p in prepare)
    knowledge = (
        "description: \"auto-derived skill (structure + grounded observables only; no priors)\"\n"
        "observable_locator:\n" + (locator or "  value: { file: \"%s\" }\n" % tier1_output) +
        "run_profiles:\n  minimal:\n"
        "    command: %s\n" % json.dumps(command) +
        "    run_in: work\n    build: []\n"
        "    prepare:\n" + prepare_yaml +
        "    tier1_output: \"%s\"\n" % tier1_output +
        "    tier2_observable: %s\n" % (tier2 or "value") +
        "    needs: []\n"
    )
    (pack / "knowledge.yaml").write_text(knowledge, encoding="utf-8")
    # extractor synthesised by gen_extractor (the single home for extractor codegen)
    (pack / "extractors.py").write_text(
        gen_extractor.generate_from_truth(truth, file_pattern=pattern)["source"],
        encoding="utf-8")
    return {
        "pack_dir": str(pack),
        "auto_derived": {
            "primary_entry": (sc.get("primary_entry") or {}).get("path"),
            "n_columns": sample["n_columns"],
            "paradigm": truth["paradigm"],
            "observables_from_header": observables,
            "tier2_observable": tier2,
        },
        "needs_prior_not_required_to_run": [
            "physical meaning of each parameter/observable",
            "physical plausibility of the produced value (e.g. expected magnitude/range)",
        ],
    }


def run_to_t2(project_root, pack_dir, work_root, command, tier1_output):
    """Generate the skill from the auto candidate and drive it to T2."""
    skill = Path(work_root) / "skill"
    gen = subprocess.run(
        [sys.executable, "-m", "engine.generate", "--project-root", str(project_root),
         "--out-dir", str(skill), "--packs-dir", str(Path(pack_dir).parent), "--force"],
        cwd=str(REPO), capture_output=True, text=True)
    if gen.returncode != 0:
        return {"error": "generate failed", "stderr": gen.stderr[-400:]}
    run = Path(work_root) / "run"
    prof = skill / "scripts" / "run_profile.json"
    extr = skill / "scripts" / "extractors.py"
    if not prof.exists():
        return {"error": "no run_profile generated (candidate did not yield a run recipe)"}
    subprocess.run(
        [sys.executable, str(skill / "scripts" / "run_launcher.py"),
         "--project-root", str(project_root), "--work-dir", str(run),
         "--run-profile", str(prof), "--extractors", str(extr), "--max-tier", "2"],
        cwd=str(REPO), capture_output=True, text=True)
    rep = run / "verification-report.json"
    if not rep.exists():
        return {"error": "no verification report produced"}
    r = json.loads(rep.read_text(encoding="utf-8"))
    return {"tier_reached": r.get("tier_reached"), "observable": r.get("observable"),
            "blockers": r.get("blockers"), "report": str(run / "verification-report.md")}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Auto-candidate skill to T2 (no physics priors).")
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--command", required=True,
                    help="JSON list, e.g. '[\"./trento\",\"Pb\",\"Pb\",\"5\",\"-o\",\"{work}/out\"]'")
    ap.add_argument("--tier1-output", required=True)
    ap.add_argument("--work-dir", default=None)
    args = ap.parse_args(argv)
    command = json.loads(args.command)
    work = Path(args.work_dir) if args.work_dir else Path(tempfile.mkdtemp(prefix="derive_demo_"))
    work.mkdir(parents=True, exist_ok=True)

    # Pass 1: run to T1 so grounding has a real output (uses the same launcher path).
    from engine import generate as _gen                       # noqa: F401
    prep_out = work / "t1"
    prep_out.mkdir(parents=True, exist_ok=True)
    cmd = [tok.replace("{work}", str(work)) for tok in command]
    # resolve a prebuilt binary './x' against the checkout if needed
    if cmd and cmd[0].startswith("./"):
        found = list(Path(args.project_root).rglob(cmd[0][2:]))
        found = [f for f in found if f.is_file() and "build" in str(f)]
        if found:
            cmd[0] = str(found[0])
    out_flag = cmd.index("-o") + 1 if "-o" in cmd else None
    if out_flag:
        cmd[out_flag] = str(prep_out)
    t1 = subprocess.run(cmd, cwd=str(Path(args.project_root)), capture_output=True, text=True)
    built = build_candidate(args.project_root, command, args.tier1_output, str(prep_out), work)
    if "error" in built:
        print(json.dumps({"stage": "build_candidate", **built,
                          "t1_stderr": t1.stderr[-300:]}, indent=2, ensure_ascii=False))
        return 1
    result = run_to_t2(args.project_root, built["pack_dir"], work, command, args.tier1_output)
    print(json.dumps({"work_dir": str(work), "auto_candidate": built, "run": result},
                     indent=2, ensure_ascii=False))
    return 0 if result.get("tier_reached") == 2 else 2


if __name__ == "__main__":
    sys.exit(main())
