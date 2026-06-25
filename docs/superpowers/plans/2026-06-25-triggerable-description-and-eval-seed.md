# Triggerable Description + Eval Seed — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the meta-skill generate skills that (A) carry a triggerable, checkout-scoped `description`, and (B) ship a starter `evals/evals.json` plus a pointer to `skill-creator` for measuring/improving the skill.

**Architecture:** Two new generic functions in `engine/generate.py` — `render_skill_description(scan, pack)` and `render_evals(scan, pack)` — filled entirely from `scan`/`pack` at generation time. `render_skill_md` uses the new description and gains a pointer section; `generate()` writes the evals file. No eval engine is built; no model name enters the engine.

**Tech Stack:** Python 3, `unittest`. Spec: `docs/superpowers/specs/2026-06-25-triggerable-description-and-eval-seed-design.md`.

## Global Constraints

- **Engine stays model-agnostic.** `render_skill_description` / `render_evals` must contain NO model name (clvisc/lbt/smash/urqmd/trento/...). All code identity, verbs, trigger phrases, and eval prompts come from `scan`/`pack` at runtime. `tests/test_boundary.py` already scans `engine/**` and must stay green.
- **The `description` must be safe inside `description: "..."`** — single line (no `\n`), no raw double quote.
- **Description is scoped, not "pushy"**: always references "this scanned checkout"; trigger phrases come ONLY from `intent_rules[].match` (user phrasing), never from `observable_locator` keys (internal codes).
- **Do not build an eval engine and do not call `skill-creator`** — only emit the seed file + a text pointer.
- Match existing style: `Dict`/`Optional` typing, `write_file(path, text)`, local helpers module-level.

---

## File Structure

- `engine/generate.py` — add `_join_and`, `render_skill_description`, `render_evals`; edit `render_skill_md` (description line + References + new section); edit `generate()` (write evals) and `_GENERATED_FILES`.
- `tests/test_generate_trigger_eval.py` — **new**; `TriggerDescriptionTest` (Task 1) + `EvalSeedTest` (Task 2).

---

## Task 1: Triggerable description (Gap A)

**Files:**
- Modify: `engine/generate.py` (add `_join_and` + `render_skill_description`; edit `render_skill_md` description line)
- Test: `tests/test_generate_trigger_eval.py`

**Interfaces:**
- Produces: `render_skill_description(scan: Dict, pack: Optional[Dict]) -> str`; `_join_and(items: List[str]) -> str`.
- Consumes: existing `render_skill_md` (replaces its hardcoded description line).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_generate_trigger_eval.py`:

```python
import json
import pathlib
import tempfile
import unittest

from engine import generate


def _scan(**kw):
    base = {"project_root": "/tmp/FooSolver", "readme_path": None,
            "primary_entry": None, "parameters": [], "output_files": [],
            "entrypoints": [], "readme_commands": [], "build_files": [],
            "build_targets": [], "dependencies": [], "git": {},
            "directories": [], "file_counts": {}}
    base.update(kw)
    return base


def _pack(_name="demo", **knowledge):
    return {"name": _name, "knowledge": knowledge}


class TriggerDescriptionTest(unittest.TestCase):
    def test_pack_description_verbs_and_triggers(self):
        scan = _scan(parameters=[{"name": "a"}], output_files=[{"name": "out.dat"}])
        pack = _pack(description="DemoCode: a toy transport model.",
                     intent_rules=[{"match": ["scan coupling", "turn off radiation"]}])
        d = generate.render_skill_description(scan, pack)
        self.assertIn("DemoCode: a toy transport model", d)
        self.assertIn("this scanned checkout of demo", d)
        self.assertIn("run it", d)
        self.assertIn("edit its parameters", d)
        self.assertIn("analyze its outputs", d)
        self.assertIn("scan coupling", d)               # human-phrasing trigger

    def test_no_pack_noun_phrase_and_scan_verbs(self):
        scan = _scan(project_root="/tmp/FooSolver",
                     primary_entry={"path": "main.py"},
                     parameters=[], output_files=[])      # nothing to configure/analyze
        d = generate.render_skill_description(scan, None)
        self.assertIn("FooSolver", d)
        self.assertIn("main.py", d)
        self.assertIn("run it", d)
        self.assertNotIn("edit its parameters", d)        # scan found no parameters
        self.assertNotIn("analyze its outputs", d)        # scan found no outputs
        self.assertNotIn(", e.g.", d)                     # no intent_rules -> no trigger clause
        self.assertNotIn("Version-specific skill for this scanned checkout", d)

    def test_yaml_single_line_safe(self):
        scan = _scan(parameters=[{"name": "a"}])
        pack = _pack(description='He said "hi"\nand more.')
        d = generate.render_skill_description(scan, pack)
        self.assertNotIn('"', d)                          # double quotes neutralized
        self.assertNotIn("\n", d)                         # single line

    def test_wired_into_skill_md(self):
        scan = _scan(parameters=[{"name": "a"}])
        pack = _pack(description="DemoCode: toy.")
        md = generate.render_skill_md(scan, pack)
        self.assertIn("DemoCode: toy", md)
        self.assertNotIn("Version-specific skill for this scanned checkout", md)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_generate_trigger_eval.TriggerDescriptionTest -v`
Expected: FAIL (`render_skill_description` does not exist / old description still present).

- [ ] **Step 3: Implement `_join_and` + `render_skill_description`**

In `engine/generate.py`, add immediately **before** `def render_skill_md`:

```python
def _join_and(items: List[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return items[0] if items else ""
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def render_skill_description(scan: Dict[str, object], pack: Optional[Dict]) -> str:
    """Trigger-facing one-line description for the generated skill. Generic:
    code identity, verbs, and trigger phrases are filled from scan/pack at
    generation time -- the engine names no model. Scoped to THIS checkout so it
    does not over-trigger on other forks/contexts."""
    knowledge = (pack or {}).get("knowledge") or {}
    code_id = (pack or {}).get("name") or Path(scan.get("project_root", "project")).name or "project"
    entry = (scan.get("primary_entry") or {}).get("path") if scan.get("primary_entry") else None
    what = knowledge.get("description")
    if not what:
        what = f"The {code_id} code" + (f" (entry `{entry}`)" if entry else "")
    what = str(what).strip().rstrip(".")
    verbs = ["run it"]                                  # always: scan found an entry
    if scan.get("parameters"):
        verbs.append("edit its parameters")
    if scan.get("output_files") or knowledge.get("observable_locator"):
        verbs.append("analyze its outputs")
    triggers: List[str] = []
    for rule in knowledge.get("intent_rules") or []:    # user-phrasing only
        for m in (rule.get("match") or []):
            m = str(m).strip()
            if m and m not in triggers:
                triggers.append(m)
    eg = f", e.g. {', '.join(triggers[:4])}" if triggers else ""
    desc = (f"{what}. Use this skill to {_join_and(verbs)} this scanned "
            f"checkout of {code_id}{eg}.")
    return " ".join(desc.split()).replace('"', "'")     # YAML single-line safe
```

Then edit the description line in `render_skill_md` (currently `generate.py:537`):

```python
        f"description: \"{render_skill_description(scan, pack)}\"\n---\n\n"
```

(replacing `f"description: \"Version-specific skill for this scanned checkout.\"\n---\n\n"`)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_generate_trigger_eval.TriggerDescriptionTest -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Run full suite + boundary**

Run: `python -m unittest discover -s tests`
Expected: OK (skipped=2); `tests.test_boundary` green (no model token introduced).

- [ ] **Step 6: Commit**

```bash
git add engine/generate.py tests/test_generate_trigger_eval.py
git commit -m "feat(skill): generate a triggerable, checkout-scoped description"
```

---

## Task 2: Eval seed + skill-creator pointer (Gap B)

**Files:**
- Modify: `engine/generate.py` (add `render_evals`; `generate()` writes `evals/evals.json`; `_GENERATED_FILES` += entry; `render_skill_md` References + new section)
- Test: `tests/test_generate_trigger_eval.py` (add `EvalSeedTest`)

**Interfaces:**
- Produces: `render_evals(scan: Dict, pack: Optional[Dict]) -> Dict` (`{"skill_name": str, "evals": [{"id","prompt","expected_output","files"}]}`).
- Consumes: existing `generated_skill_name(scan, pack)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_generate_trigger_eval.py`:

```python
class EvalSeedTest(unittest.TestCase):
    def test_from_demos(self):
        pack = _pack(demos=[
            {"title": "t1", "intent": "run the minimal case", "args": {"cent": "0_5"}},
            {"title": "t2", "intent": "scan the coupling"},
        ])
        out = generate.render_evals(_scan(), pack)
        self.assertEqual(out["skill_name"], generate.generated_skill_name(_scan(), pack))
        self.assertEqual(len(out["evals"]), 2)
        e0 = out["evals"][0]
        self.assertIn("run the minimal case", e0["prompt"])
        self.assertIn("cent=0_5", e0["prompt"])           # args surfaced
        self.assertEqual(e0["files"], [])
        self.assertTrue(e0["expected_output"])

    def test_from_intent_rules_when_no_demos(self):
        pack = _pack(intent_rules=[{"match": ["scan coupling"]}])
        out = generate.render_evals(_scan(), pack)
        self.assertEqual(len(out["evals"]), 1)
        self.assertIn("scan coupling", out["evals"][0]["prompt"])

    def test_generic_when_no_pack(self):
        out = generate.render_evals(_scan(), None)
        self.assertEqual(len(out["evals"]), 1)
        self.assertIn("minimal example", out["evals"][0]["prompt"])

    def test_generate_writes_evals_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "src"
            root.mkdir()
            out = pathlib.Path(tmp) / "skill"
            generate.generate(_scan(project_root=str(root)), None, out)
            ev = out / "evals" / "evals.json"
            self.assertTrue(ev.exists())
            data = json.loads(ev.read_text(encoding="utf-8"))
            self.assertIn("skill_name", data)
            self.assertTrue(data["evals"])

    def test_skill_md_points_to_skill_creator(self):
        md = generate.render_skill_md(_scan(), None)
        self.assertIn("Evaluating & Improving", md)
        self.assertIn("skill-creator", md)
        self.assertIn("evals/evals.json", md)

    def test_evals_in_generated_files(self):
        self.assertIn("evals/evals.json", generate._GENERATED_FILES)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_generate_trigger_eval.EvalSeedTest -v`
Expected: FAIL (`render_evals` missing; evals file not written; pointer absent).

- [ ] **Step 3a: Implement `render_evals`**

In `engine/generate.py`, add after `render_skill_description`:

```python
def render_evals(scan: Dict[str, object], pack: Optional[Dict]) -> Dict[str, object]:
    """Starter eval prompts for skill-creator (prompts only; skill-creator adds
    assertions). Generic: derived from pack demos / intent_rules, else one
    generic prompt. The engine names no model."""
    knowledge = (pack or {}).get("knowledge") or {}
    evals: List[Dict] = []
    for demo in (knowledge.get("demos") or [])[:3]:
        intent = str(demo.get("intent") or demo.get("title") or "").strip()
        if not intent:
            continue
        prompt = f"Using this skill, {intent}."
        args = demo.get("args") or {}
        if args:
            prompt += " Suggested settings: " + ", ".join(f"{k}={v}" for k, v in args.items()) + "."
        evals.append({"id": len(evals) + 1, "prompt": prompt,
                      "expected_output": intent, "files": []})
    if not evals:
        for rule in (knowledge.get("intent_rules") or [])[:3]:
            matches = rule.get("match") or []
            if not matches:
                continue
            intent = str(matches[0]).strip()
            evals.append({"id": len(evals) + 1,
                          "prompt": f"Using this skill, {intent}.",
                          "expected_output": f"a correct result for: {intent}",
                          "files": []})
    if not evals:
        evals.append({"id": 1,
                      "prompt": "Run this code's documented minimal example and report its primary output.",
                      "expected_output": "the minimal run completes and the primary output is produced",
                      "files": []})
    return {"skill_name": generated_skill_name(scan, pack), "evals": evals}
```

- [ ] **Step 3b: `generate()` writes the evals file**

In `generate()`, immediately after the README block:

```python
    status = readme_status(scan)
    if status != "ok":
        write_file(out_dir / "references/generated-README.md", render_readme(scan, pack))
    write_file(out_dir / "evals/evals.json", json.dumps(render_evals(scan, pack), indent=2))
```

- [ ] **Step 3c: Register for stale cleanup**

In the `_GENERATED_FILES` list, after `"references/generated-README.md",` add:

```python
    "evals/evals.json",
```

- [ ] **Step 3d: SKILL.md References entry + pointer section**

In `render_skill_md`, change the model-gaps References line (`generate.py:566`) to add the evals entry:

```python
        f"- `references/model-gaps.md`\n"
        f"- `evals/evals.json` (starter eval tasks for skill-creator)\n\n"
```

And change the end of the "If Blocked" block (`generate.py:582`) to insert the new section before `{intent}`:

```python
        f"then re-run validation.\n\n"
        f"## Evaluating & Improving This Skill\n\n"
        f"This skill was auto-generated. To measure whether it actually helps an agent "
        f"on real tasks -- and to improve it -- run the `skill-creator` skill on this "
        f"directory. Starter test tasks are in `evals/evals.json`; skill-creator runs "
        f"them with and without this skill, grades the results, and iterates.\n"
        f"{intent}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_generate_trigger_eval.EvalSeedTest -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Run full suite + boundary**

Run: `python -m unittest discover -s tests`
Expected: OK (skipped=2). Confirms `_GENERATED_FILES` change didn't break `test_generate_full` cleanup and boundary stays green.

- [ ] **Step 6: Commit**

```bash
git add engine/generate.py tests/test_generate_trigger_eval.py
git commit -m "feat(skill): seed evals/evals.json + point to skill-creator for eval"
```

---

## Notes for the implementer

- Task 1 and Task 2 both edit `render_skill_md`; Task 2 sees Task 1's description change already in place — keep both edits.
- `json` is already imported at the top of `generate.py`; no new import needed.
- Do not add assertions to the evals (skill-creator owns those). Do not invoke skill-creator anywhere.
- If `render_evals` ever needs the project name and there is no pack, `generated_skill_name` already handles the fallback — reuse it, don't reimplement.
