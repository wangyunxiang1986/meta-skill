---
name: project-explorer-and-skill-creator
description: >
  Use when asked to explore a scientific/engineering code package and create a
  reusable, version-specific skill for that exact checkout, then validate it by
  actually running a minimal task. Triggers include "帮我探索这个程序", "深入理解这个
  程序包并创建一个可用技能", and CLVisc/SMASH/URQMD-style simulation packages.
---

# Project Explorer And Skill Creator

This meta skill has **three main modules**: **1 扫描 (Scan)**,
**2 构造 Skill (Compose)**, and **3 测试 Skill (Validate + Iterate)**. Internally,
those modules execute a six-step loop: scan source code, build project profile,
compose a generated skill, validate by tiered test run, record evidence, and iterate
the generated skill or knowledge pack. It scans a code checkout, builds a
version-specific project profile, composes a reusable skill, test-runs it on a minimal
task, records success/blocker evidence, and iterates until the generated skill is
usable. The **engine** (`engine/`) is model-agnostic; **knowledge packs**
(`packs/<model>/`) add domain meaning; with no pack the result is structural but still
usable.

Resolve `<PROJECT_ROOT>` (the checkout) and `<WORK_DIR>` (a writable scratch dir;
write ALL artifacts here, never into the source tree).

## 1 扫描 (Scan)

### 1.1 扫源码  →  `project-understanding.md`

1. Produce the understanding draft (it scans the tree via `engine.scan` internally):
   ```bash
   python -m engine.understanding --project-root "<PROJECT_ROOT>" \
     --out "<WORK_DIR>/project-understanding.md"
   ```
2. Read README/docs/headers; enrich the draft's narrative (physics goal, module→file
   mapping). Keep the `source-derived` vs `inferred` markers honest. If no pack matched,
   say so and point to `references/model-gaps.md`.

### 1.2 建立项目画像 (Project Profile)

The scan must identify the program's functionality, inputs, configs, modules,
functions/entry points, outputs, code structure, README run commands, dependencies,
build requirements, version fingerprint, and human-review gaps. Treat structural facts
as source-derived; mark domain meanings from packs or human inference explicitly.

## 2 构造 Skill (Compose)

### 2.1 生成 version-specific skill

```bash
python -m engine.generate --project-root "<PROJECT_ROOT>" \
  --out-dir "<WORK_DIR>/generated-skill" --packs-dir packs
```
**Existing skill?** If `<WORK_DIR>/generated-skill/SKILL.md` already exists, this step is
skipped (reported as `"skipped": true`) and the workflow proceeds directly to validation
(module 3). Pass `--force` to regenerate over an existing skill.

Produces `SKILL.md` + `references/*` + `scripts/*` (verify_environment, analyze_outputs,
and — when a pack supplies run_profiles — `run_launcher.py` + `run_profile.json` + `extractors.py`).
The generated product has three layers: `SKILL.md` (程序功能 / 何时调用) · `references/*`
(project profile, understanding, parameters incl. constraints, outputs, run-modes,
**demos**, verified-runs, blocked-runs, model-gaps) · `scripts/*` (`config.py` for
parameter checks, `run.py`/`run_launcher.py` for execution, `analysis.py` for output
analysis, `visualize.py` for diagnostics, plus run_profile/constraints/extractors).

## 3 测试 Skill (Validate + Iterate)

### 3.1 分层验证  →  `verification-report.md`

Best-effort to the deepest tier the environment allows; **do not silently** treat a
blocked deeper tier as success.
```bash
python "<WORK_DIR>/generated-skill/scripts/run_launcher.py" \
  --project-root "<PROJECT_ROOT>" --work-dir "<WORK_DIR>/run" \
  --run-profile "<WORK_DIR>/generated-skill/scripts/run_profile.json" \
  --extractors "<WORK_DIR>/generated-skill/scripts/extractors.py" \
  --cent 0_5 --gpu 0 --max-tier 2
```
- T0 verify + dry-run; T1 real run to first non-empty output; T2 extract one observable + plot.
- The launcher writes `verification-report.md` (tier reached, command, blockers).
- If a deeper tier is blocked (missing OpenCL/build/module), report the blocker and its
  fix; the report stops at the tier actually reached.

### 3.2 记录经验 (Record Evidence)

Append successful runs to `references/verified-runs.md` and blocked runs to
`references/blocked-runs.md`. Include the tier reached, resolved command, output or
blocker, and the date. Do not overwrite earlier evidence.

### 3.3 迭代更新 (Iterate)

Then **confirm + iterate**: present to the user `project-understanding.md`, the generated
skill's capabilities, and `verification-report.md` (which tier was reached). Ask them to
confirm parameter meanings, run flow, and that the observable is what they care about. On
feedback, edit the relevant `packs/<model>/` (knowledge.yaml / extractors.py), then loop back to module 2 to regenerate the skill and re-test.

## Behavioral Norms

- **non-destructive**: read source only; write every artifact under `<WORK_DIR>`.
- **do not silently** fail: missing OpenCL/GSL/Boost/build/module are reported with fixes.
- Keep a log of each step under `<WORK_DIR>`.
- **Platform format**: `SKILL.md` (name+description) is the portable core (Claude Code uses
  it directly); `agents/openai.yaml` is the Codex manifest; for other platforms (e.g. Kimi)
  detect the required skill format first, then emit it.

## Adding a model

Add `packs/<model>/{manifest.yaml, knowledge.yaml, extractors.py}` (copy `packs/_template/`).
The engine needs no change; an unmatched checkout falls back to a generic structural skill.
