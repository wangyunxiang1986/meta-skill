# Meta Skill Framework Alignment Design

## Purpose

Align `project-explorer-and-skill-creator` with the hand-drawn framework:

1. An agent invokes a meta skill.
2. The meta skill scans a source-code checkout.
3. It composes a version-specific generated skill.
4. It test-runs the generated skill.
5. It records success/failure evidence and iteratively updates the skill.

The current implementation already follows the broad `scan -> compose -> validate`
shape. This design makes that shape explicit, adds the missing project-profile
layer, makes the generated skill package easier for an agent to use, and closes
the validation-to-iteration loop.

## Target Workflow

The meta skill should present and execute this workflow:

```text
Agent
  -> Meta skill
      1. Scan source code
      2. Build project profile
      3. Compose generated skill
      4. Validate by tiered test run
      5. Record evidence
      6. Iterate generated skill or knowledge pack
```

This is a refinement of the current three-step flow. `Scan` remains step 1, but
it now produces a machine-readable and human-readable project profile. `Compose`
uses that profile plus an optional knowledge pack to generate a skill package.
`Validate` is explicitly responsible for test running, recording success/failure,
and feeding changes back into the generated skill or the pack.

## Phase 1: Scan And Project Profile

The scan phase should produce two artifacts:

- `project-profile.json`: machine-readable facts extracted from the checkout.
- `project-understanding.md`: human/agent-readable explanation of the same facts.

The profile should include:

- program functionality, with `source-derived` vs `inferred` markers;
- directory and code structure;
- modules and entry points;
- detected functions or callable drivers;
- input files and config files;
- parameters and defaults;
- output files and likely observables;
- README run commands;
- dependency and build requirements;
- version fingerprint: git commit, describe, dirty state, remote if available;
- human-review gaps.

The engine should only extract structural facts. Domain interpretation belongs in
knowledge packs or human review notes.

## Phase 2: Compose Generated Skill

The generated skill should be a complete package:

```text
generated-skill/
  SKILL.md
  references/
    project-understanding.md
    project-profile.json
    parameters.md
    outputs.md
    run-modes.md
    demos.md
    verified-runs.md
    blocked-runs.md
    model-gaps.md
  scripts/
    config.py
    run.py
    analysis.py
    visualize.py
    run_profile.json
    param_constraints.json
    extractors.py
```

The generated `SKILL.md` should not be only an index. It should explain:

- what the scanned program does;
- when the agent should use this generated skill;
- the supported workflow;
- how to use `references/`;
- how to use each script;
- which demos are validated;
- what to do when validation is blocked.

The current `run_launcher.py` can remain internally, but the public generated
skill should expose intuitive script roles:

- `config.py`: edit and validate parameters, including allowed ranges and
  mutually exclusive settings;
- `run.py`: resolve paths, environment, command invocation, and execution;
- `analysis.py`: extract observables from outputs;
- `visualize.py`: generate diagnostic plots.

These files may wrap existing implementation logic. The important framework
change is that the generated skill presents the same conceptual script layout as
the hand-drawn design.

## Phase 3: Validate By Tiered Test Run

Validation should remain tiered, but the framework should name each tier clearly:

- T0: environment and dependency check;
- T1: command/config dry-run or command resolution;
- T2: minimal real run to first non-empty output;
- T3: physical observable extraction;
- T4: diagnostic visualization.

The generated skill must never report a blocked deeper tier as success. It should
record the deepest tier reached and the exact blocker.

Validation output should include:

- `verification-report.md`;
- `verification-report.json`;
- appended `references/verified-runs.md` for successful tiers;
- appended `references/blocked-runs.md` for failed or blocked tiers.

## Phase 4: Iterate And Update

After validation, the meta skill should classify the result:

- environment issue;
- missing external build;
- wrong command;
- wrong config path;
- wrong argument mapping;
- missing expected output;
- analysis failure;
- visualization failure;
- domain-meaning gap.

Depending on the class, it should update:

- generated `SKILL.md` for usage or failure-handling guidance;
- `references/run-modes.md` for corrected commands;
- `references/model-gaps.md` for unresolved expert questions;
- `scripts/config.py`, `run.py`, `analysis.py`, or `visualize.py` for runnable
  workflow fixes;
- the source knowledge pack when the issue is model-level and should apply to
  future generated skills.

Then it should regenerate and revalidate.

## Engine And Knowledge Pack Boundary

The framework keeps the current boundary:

- `engine/`: generic scanning, composition, validation orchestration, no model
  physics or code-specific tokens.
- `packs/<model>/`: domain knowledge, parameter meanings, output meanings,
  observable extractors, and minimal run-profile rules.
- `generated-skill/`: version-specific skill for the exact scanned checkout.

Hardcoded model paths should not live in the engine. Pack defaults are allowed,
but generated skills should validate that those defaults exist in the scanned
checkout and fall back to discovered candidates or report a blocker.

## Required Implementation Changes

1. Update the meta `SKILL.md` so it describes the six-stage framework:
   scan, project profile, compose, validate, record evidence, iterate.
2. Generate `references/project-profile.json` and copy/render
   `references/project-understanding.md` into the generated skill.
3. Make generated `SKILL.md` richer: purpose, when to use, workflow, script roles,
   demos, validation status, and blocked-run handling.
4. Add public script wrappers or aliases for `run.py`, `analysis.py`, and
   `visualize.py`, while preserving existing internals where practical.
5. Append verified and blocked run records instead of overwriting them.
6. Treat missing `base_config` as a T0 blocker rather than creating an empty
   config file.
7. Redact local absolute paths from generated references by replacing the scanned
   root with `<PROJECT_ROOT>`.
8. Generate version-specific skill names using pack/project identity plus git
   fingerprint when available.
9. Replace local absolute-path integration tests with fixtures or environment
   variables.

## Out Of Scope

- Rewriting the entire engine as a plugin system.
- Adding full semantic call-graph analysis for arbitrary scientific codes.
- Automatically installing missing system dependencies.
- Modifying the scanned target project source tree.

## Acceptance Criteria

- The meta skill documentation matches the hand-drawn framework.
- Generated skills contain `SKILL.md`, `references/`, and `scripts/` with clear
  responsibilities.
- Generated references do not leak local absolute roots.
- Validation records both successes and blockers.
- Missing config paths fail clearly at T0.
- Existing unittest suite passes.
- At least one synthetic fixture proves the framework works without local
  absolute paths.

## Self Review

- No open TODO/TBD placeholders remain.
- Scope is limited to framework alignment and immediate robustness changes.
- The design preserves the current engine/pack boundary.
- The design does not require modifying user source checkouts.
