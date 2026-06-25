# project-explorer-and-skill-creator

A meta-skill that scans a scientific/engineering code checkout and **generates a
reusable, version-specific skill** for that exact checkout — then validates the
generated skill by *actually running* a minimal task end-to-end.

The framework has **three main modules**:

```text
1. Scan
2. Compose Skill
3. Validate Skill
```

Operationally, these modules execute a six-step loop:

```text
Scan:
  1. scan source code
  2. build project profile
Compose Skill:
  3. compose generated skill
Validate Skill:
  4. validate by tiered test run
  5. record success/failure evidence
  6. iterate generated skill or knowledge pack
```

This matches the intended skill-creation workflow: the meta skill first builds a
project image (functionality, inputs/configs, modules/functions, outputs, code
structure, README run commands, dependencies), then writes a complete skill package
with references, demos, and executable scripts, then test-runs and updates it using
runtime evidence.

The design is **generic engine + thin knowledge packs**:

- **`engine/`** — model-agnostic. It only extracts *structural* facts (entry points,
  parameters, outputs, build targets, README run commands) and assembles a skill.
  It contains **no** domain/model knowledge; `tests/test_boundary.py` enforces that
  (no model tokens, no `import packs`).
- **`packs/<model>/`** — all domain knowledge for one model lives here
  (parameter meanings, output meanings, observable extraction, run knobs).
  Adding a model = add a pack; **the engine never changes**. An unmatched checkout
  still produces a valid (structural-only) skill.

---

## Why

The same simulation code (e.g. CLVisc) exists in many divergent forks: different
entry scripts, argument orders, config styles, output layouts. Hand-writing one
skill per fork doesn't scale. This meta-skill **derives** the run recipe from each
checkout instead of hardcoding it, so one engine + one pack covers every fork.

Nothing version-specific is hardcoded. The launch command is derived, in order:

1. **README** — if the README documents how to run the primary entry, use it
   (it carries real example values).
2. **Cross-check** — the command must supply every positional arg the code actually
   reads. The required count is inferred from the code itself: the highest
   `sys.argv[i]` index **and** any `len(sys.argv) <op> N` guard. If the README
   documents *fewer* args than the code requires, the README is **stale** → it is
   ignored and the command is reconstructed from the code.
3. **Code reconstruction** — argument names come from the script's own
   `name = sys.argv[i]` assignments. Semantic slots (`config`/`cent`/`gpu`) become
   `{placeholders}` filled at run time; a positional the pack can't name is emitted
   as a `<name>` placeholder for the **user** to fill (the meta-skill never guesses
   a value, and model-specific values never leak into the engine).

---

## Requirements

- **Python 3** (standard library only for the engine core).
- **PyYAML** — the engine reads pack manifests/knowledge (`pip install pyyaml`).
- A pack's `extractors.py` may need more: the bundled **clvisc** pack uses
  **numpy** + **matplotlib** to extract observables and plot.
- Plus whatever the *target checkout* itself needs to actually run (compilers,
  OpenCL, etc.). Those are reported by the T0 environment check, not installed automatically.

### Dependency completion policy

The hand-written workflow includes "补齐库" (fill missing libraries). This meta-skill
keeps that step **non-destructive by default**: it detects missing Python modules,
OpenCL, build directories, and other declared needs, then records them as blockers in
`verification-report.md` / `references/blocked-runs.md`. It does not run `pip`,
`conda`, system package managers, or build commands unless the user explicitly opts in
and the executing agent has permission to modify the environment.

## Quick start

The command-line usage follows the three main modules above. Internally those commands
cover the six-step loop (scan/profile, compose, validate/record/iterate). Standalone, against
any checkout:

```bash
cd project-explorer-and-skill-creator

# Module 1 — 扫描 (Scan): structural understanding draft + project profile
python -m engine.understanding --project-root <PROJECT_ROOT> \
  --out <WORK_DIR>/project-understanding.md

# Module 2 — 构造 skill (Compose): generate the version-specific skill
python -m engine.generate --project-root <PROJECT_ROOT> \
  --out-dir <WORK_DIR>/generated-skill --packs-dir packs

# Module 3 — 测试 skill (Validate): tiered real run + evidence + iteration
python <WORK_DIR>/generated-skill/scripts/run_launcher.py \
  --project-root <PROJECT_ROOT> --work-dir <WORK_DIR>/run \
  --run-profile <WORK_DIR>/generated-skill/scripts/run_profile.json \
  --extractors  <WORK_DIR>/generated-skill/scripts/extractors.py \
  --cent 0_5 --gpu 0 --max-tier 2
```

`<PROJECT_ROOT>` is the checkout; `<WORK_DIR>` is a writable scratch dir. **All
artifacts go to `<WORK_DIR>`; the source tree is read-only.** If the project is
nested inside a wrapper directory (e.g. an unzipped archive `wrapper/Project/...`),
both the scanner and the launcher auto-descend to the real root.

> **Step 3 applies only when a knowledge pack matched.** The
> `run_launcher.py` / `run_profile.json` / `extractors.py` are generated only when
> the matched pack supplies a `run_profiles` entry. With no pack, the generated skill
> is structural-only (Steps 1–2); there is nothing to launch in Step 3.

### Tiers (validation)

| Tier | Meaning |
|------|---------|
| T0   | verify environment + resolve command (no execution) |
| T1   | real run to the first non-empty output |
| T2   | extract one observable from that output + plot |

The launcher writes `verification-report.md` recording the tier reached, the
resolved command, and any blockers. A blocked deeper tier is **never** silently
treated as success.

---

## Generated skill layout

```
generated-skill/
├── SKILL.md                 # purpose, when to use, workflow, references, scripts
├── references/
│   ├── project-profile.json # machine-readable scanned project facts
│   ├── project-understanding.md # human/agent-readable project profile
│   ├── parameters.md        # params + meanings + choices/range + required + mutual-exclusion
│   ├── outputs.md           # output files with meanings
│   ├── run-modes.md         # derived run command(s)
│   ├── demos.md             # derived baseline + pack-curated worked demos
│   ├── verified-runs.md     # 固化: known-good command + tier (written by a real run)
│   ├── blocked-runs.md      # blocked attempts + exact blocker
│   └── model-gaps.md        # what a human/pack still needs to fill
└── scripts/
    ├── config.py            # set/check parameters, constraints, ranges, exclusivity
    ├── run.py               # public run entry; wraps run_launcher.py when available
    ├── analysis.py          # public analysis entry; wraps analyze_outputs.py
    ├── visualize.py         # diagnostic visualization/report entry
    ├── verify_environment.py
    ├── analyze_outputs.py   # low-level output summary helper
    ├── run_launcher.py      # low-level tiered launcher when a pack supplies run_profiles
    ├── run_profile.json     # derived command_argv + run knobs
    ├── param_constraints.json  # actionable constraints (choices/range/exclusion) for config.py
    └── extractors.py        # pack's observable extractors
```

---

## Repository layout

```
engine/                      # model-agnostic (guarded by test_boundary.py)
├── scan.py                  # entry points, params, outputs, builds, README cmds,
│                            #   argv-required-count inference, wrapper auto-descent
├── generate.py              # assemble skill; command derivation + README cross-check
├── pack_loader.py           # match + load a knowledge pack from its manifest
├── understanding.py         # project-understanding.md (source-derived vs inferred)
└── templates/               # files copied into every generated skill
    ├── verify_environment.py
    ├── analyze_outputs.py
    └── run_launcher.py       # generic tiered T0/T1/T2 launcher (argv list, no shell)

packs/
├── clvisc/                  # CLVisc knowledge
│   ├── manifest.yaml        # match rule (file_exists / readme_contains)
│   ├── knowledge.yaml       # param/output meanings, observable_locator,
│   │                        #   intent_rules, run_profiles (arg_map slots + defaults)
│   └── extractors.py        # extract/fit observables (e.g. dNch/deta, v2)
└── _template/               # empty scaffold for a new model

tests/                       # unittest suite (incl. the engine boundary guard)
SKILL.md                     # the six-stage agent workflow
agents/openai.yaml           # Codex manifest (SKILL.md is the portable core)
```

---

## Adding a model

```bash
cp -r packs/_template packs/<model>
```

Fill three files; the engine needs no change:

- **`manifest.yaml`** — a match rule (`any_of` of `file_exists:` / `readme_contains:`).
- **`knowledge.yaml`** — `param_meaning`, `output_meaning`, `observable_locator`,
  `intent_rules`, and `run_profiles` (with a `driver.arg_map` mapping semantic slots
  to argument-name patterns, plus per-name `arg_defaults`). Optional:
  `param_constraints` (per-param `range` / `exclusive_with` / `note` — supplements
  argparse-scanned `choices`/`required`/mutex groups) and `demos` (list of
  `{title, intent, args}` worked examples).
- **`extractors.py`** — an `extract(observable, out_dir, analysis_dir)` function.

`run_profiles[*].driver` must **not** contain a literal command — the command is
derived from the checkout. The pack supplies only slot patterns and the values it
legitimately owns; anything it can't name is left as a `<placeholder>` for the user.

---

## Tests

```bash
python -m unittest discover -s tests
```

The boundary test (`tests/test_boundary.py`) asserts the engine carries no
model-specific tokens and never imports a pack, keeping the engine truly generic.

---

## Validation status

Validated end-to-end on two divergent CLVisc forks:

- **dev_stable** (`CLVisc.py`, TRENTo IC, no README run command) →
  derived `python CLVisc.py {config} {cent} {gpu} 0 1` → real run to **T2**
  (TRENTo → viscous hydro → freeze-out surface → `hypersf.dat` → dN_ch/dη + plot).
- **public xyw2016/clvisc** (`ebe_trento.py`) →
  `python ebe_trento.py auau200 0_5 0 0 1` → TRENTo (oneshot) → viscous hydro →
  freeze-out surface (`hypersf.dat`, ~53k cells). The upstream comments out
  particlization, so it stops at the freeze-out surface by design.
