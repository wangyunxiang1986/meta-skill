# Meta Skill Framework Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align `project-explorer-and-skill-creator` with the approved scan-profile-compose-validate-record-iterate framework.

**Architecture:** Keep the existing generic `engine/` plus `packs/` boundary. Add a project-profile artifact, richer generated skill text, public script role wrappers, path redaction, version-specific generated names, and validation evidence append behavior.

**Tech Stack:** Python standard library, PyYAML for packs, unittest tests, Markdown skill documentation.

---

## File Structure

- Modify `SKILL.md`: describe the six-stage meta-skill framework matching the hand-drawn design.
- Modify `engine/scan.py`: keep structural scanning, expose redacted/relative paths where generated references need them.
- Modify `engine/understanding.py`: render project understanding with `<PROJECT_ROOT>` instead of local absolute roots.
- Modify `engine/generate.py`: generate version-specific skill names, copy `project-profile.json`, produce richer generated `SKILL.md`, redact paths in reference tables, and create public script wrappers.
- Modify `engine/templates/run_launcher.py`: treat missing `base_config` as T0 blocker; append verified/blocked run evidence.
- Modify `engine/templates/analyze_outputs.py`: recurse through output directories.
- Create `engine/templates/run.py`, `engine/templates/analysis.py`, `engine/templates/visualize.py`: public script roles that wrap existing implementation where possible.
- Modify `tests/`: add fixture-based tests for version names, path redaction, missing config blockers, appended evidence, and generated layout.
- Update `README.md`: document the six-stage framework and generated layout.

---

### Task 1: Meta Skill Documentation

**Files:**
- Modify: `SKILL.md`
- Modify: `README.md`

- [ ] **Step 1: Update `SKILL.md` to the six-stage framework**

Replace the current three-step wording with:

```markdown
A closed loop in six stages: scan source code -> build project profile -> compose a generated skill -> validate by tiered test run -> record evidence -> iterate generated skill or knowledge pack.
```

Keep existing commands, but group them under the six stages.

- [ ] **Step 2: Update `README.md` framework description**

Add the same six-stage description near the top and explain that the generated skill exposes `config.py`, `run.py`, `analysis.py`, and `visualize.py` roles.

- [ ] **Step 3: Run documentation smoke check**

Run:

```bash
python -m unittest tests.test_skill_md -q
```

Expected: tests pass or only fail on assertions that need updating for the new wording.

---

### Task 2: Project Profile And Path Redaction

**Files:**
- Modify: `engine/generate.py`
- Modify: `engine/understanding.py`
- Test: `tests/test_generate_refs.py`
- Test: `tests/test_understanding.py`

- [ ] **Step 1: Add path redaction helper tests**

Add tests asserting that generated references replace the scanned root with `<PROJECT_ROOT>` and do not contain local absolute home paths.

- [ ] **Step 2: Implement redaction helper**

Add a helper in `engine/generate.py`:

```python
def redact_project_path(value, project_root):
    text = str(value)
    root = str(project_root or "")
    if root and text.startswith(root):
        return "<PROJECT_ROOT>" + text[len(root):]
    return text
```

Use it when rendering parameter sources, output sources, and project identity.

- [ ] **Step 3: Write `project-profile.json`**

During `generate()`, write the full scan dictionary to:

```text
references/project-profile.json
```

with root paths redacted.

- [ ] **Step 4: Copy/render `project-understanding.md` into generated references**

Use `understanding.render_project_understanding(scan, pack)` and write it to:

```text
references/project-understanding.md
```

- [ ] **Step 5: Run targeted tests**

Run:

```bash
python -m unittest tests.test_generate_refs tests.test_understanding -q
```

Expected: pass.

---

### Task 3: Version-Specific Generated Skill

**Files:**
- Modify: `engine/generate.py`
- Test: `tests/test_skill_md.py`
- Test: `tests/test_generate_full.py`

- [ ] **Step 1: Add tests for generated skill name**

Assert that generated `SKILL.md` name includes pack name plus a project/version fingerprint when scan git data exists.

- [ ] **Step 2: Implement generated skill identity**

Add:

```python
def generated_skill_name(scan, pack):
    base = (pack or {}).get("name", "generated-project-skill")
    root_name = Path(scan.get("project_root", "project")).name.lower().replace("_", "-")
    describe = ((scan.get("git") or {}).get("describe") or "").lower().replace("/", "-")
    parts = [base, root_name]
    if describe:
        parts.append(describe)
    return "-".join(p for p in parts if p)
```

Sanitize to letters, numbers, and hyphens.

- [ ] **Step 3: Enrich generated `SKILL.md`**

Include sections:

- What this program does
- When to use this skill
- Workflow
- References
- Scripts
- Demos
- Validation status
- If blocked

- [ ] **Step 4: Run targeted tests**

Run:

```bash
python -m unittest tests.test_skill_md tests.test_generate_full -q
```

Expected: pass.

---

### Task 4: Public Script Roles

**Files:**
- Create: `engine/templates/run.py`
- Create: `engine/templates/analysis.py`
- Create: `engine/templates/visualize.py`
- Modify: `engine/generate.py`
- Modify: `engine/templates/analyze_outputs.py`
- Test: `tests/test_generate_full.py`

- [ ] **Step 1: Add generated layout test**

Assert generated skills contain:

```text
scripts/config.py
scripts/run.py
scripts/analysis.py
scripts/visualize.py
```

- [ ] **Step 2: Create `run.py` wrapper**

Implement a small wrapper that invokes sibling `run_launcher.py` with the same CLI arguments when present.

- [ ] **Step 3: Create `analysis.py` wrapper**

Implement a wrapper around `analyze_outputs.py`.

- [ ] **Step 4: Create `visualize.py`**

Implement a minimal diagnostic visualizer that reads `summary.json` and writes a simple text report when plotting dependencies are unavailable.

- [ ] **Step 5: Make `analyze_outputs.py` recursive**

Change `run.glob(g)` to `run.rglob(g)`.

- [ ] **Step 6: Copy wrappers in `generate()`**

Copy `run.py`, `analysis.py`, and `visualize.py` into generated `scripts/`.

- [ ] **Step 7: Run targeted tests**

Run:

```bash
python -m unittest tests.test_generate_full -q
```

Expected: pass.

---

### Task 5: Validation Evidence And Missing Config Blocker

**Files:**
- Modify: `engine/templates/run_launcher.py`
- Test: `tests/test_run_launcher.py`

- [ ] **Step 1: Add missing base config test**

Create a run profile with `base_config` pointing to a missing file. Run launcher with `--max-tier 0`. Assert report contains a blocker and no empty config is treated as valid.

- [ ] **Step 2: Add append evidence tests**

Run `_write()` twice with tier 1 and blocker reports. Assert `verified-runs.md` and `blocked-runs.md` append entries rather than overwrite.

- [ ] **Step 3: Implement missing config blocker**

Before reading base config, if it does not exist:

```python
report["blockers"].append(f"base_config missing: {base}")
_write(report, work, args.run_profile)
return 0
```

- [ ] **Step 4: Implement append evidence**

Replace `write_text` in `_write_verified_run()` with append behavior and add `_write_blocked_run()`.

- [ ] **Step 5: Run targeted tests**

Run:

```bash
python -m unittest tests.test_run_launcher -q
```

Expected: pass.

---

### Task 6: Full Verification

**Files:**
- All modified files

- [ ] **Step 1: Run full unittest suite**

Run:

```bash
python -m unittest discover -q
```

Expected: all tests pass.

- [ ] **Step 2: Inspect generated example**

Generate a skill from an existing fixture or available CLVisc checkout into `/tmp/meta-skill-check` and verify generated references do not contain local absolute home paths.

- [ ] **Step 3: Summarize changes**

Report modified files, test commands, and any known remaining limitations.

---

## Self Review

- Spec coverage: all accepted design requirements map to tasks above.
- Placeholder scan: no TODO/TBD placeholders are present.
- Type consistency: functions named in tests and implementation are consistent.
- Scope: implementation is limited to framework alignment, generated layout, path redaction, and validation evidence.
