# Reusable Output Contract

A generated skill must let a future agent:

- Identify the project kind + version fingerprint (`references/project-map.md`,
  `generation-report` / git fields).
- Map common intents to concrete parameters/commands for THIS checkout
  (`references/parameters.md`, `references/run-modes.md`, pack `intent_rules`).
- Generate a safe run dir and command plan (`scripts/run_launcher.py` + `run_profile.json`).
- Extract observables into structured summaries + plots (`scripts/extractors.py`,
  `scripts/analyze_outputs.py`).
- State exactly what was verified and at which tier (`verification-report.md`).

All reusable artifacts use placeholders (`<PROJECT_ROOT>`, `<WORK_DIR>`, `<RUN_ROOT>`,
`<SKILL_DIR>`); never embed personal/cluster paths.
