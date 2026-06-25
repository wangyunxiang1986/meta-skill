"""Select and load an optional knowledge pack for a scanned checkout.

A pack lives in ``packs/<model>/`` with ``manifest.yaml`` (match rule),
``knowledge.yaml`` (data) and optional ``extractors.py`` (code). The engine
selects a pack purely from the manifest match rule evaluated against the scan;
no model name is hardcoded here.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Dict, Optional

import yaml


def _match(rule: Dict[str, object], root: Path, readme_text: str) -> bool:
    for cond in rule.get("any_of", []) or []:
        if "file_exists" in cond and (root / cond["file_exists"]).exists():
            return True
        if "readme_contains" in cond and str(cond["readme_contains"]).lower() in readme_text.lower():
            return True
    return False


def select_pack(packs_dir: Path, scan: Dict[str, object], root: Path) -> Optional[Dict[str, object]]:
    packs_dir = Path(packs_dir)
    if not packs_dir.is_dir():
        return None
    # The scan may have descended into a wrapper dir; match against the effective
    # root it actually used, not the caller's possibly-outer path.
    root = Path(scan.get("project_root") or root)
    readme_rel = scan.get("readme_path")
    readme_text = ""
    if readme_rel and (root / readme_rel).exists():
        readme_text = (root / readme_rel).read_text(encoding="utf-8", errors="replace")
    for pack_dir in sorted(p for p in packs_dir.iterdir() if p.is_dir() and not p.name.startswith("_")):
        manifest_path = pack_dir / "manifest.yaml"
        if not manifest_path.exists():
            continue
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        if _match(manifest.get("match", {}) or {}, root, readme_text):
            knowledge_path = pack_dir / "knowledge.yaml"
            knowledge = {}
            if knowledge_path.exists():
                knowledge = yaml.safe_load(knowledge_path.read_text(encoding="utf-8")) or {}
            extractors = pack_dir / "extractors.py"
            return {
                "name": manifest.get("name", pack_dir.name),
                "dir": str(pack_dir),
                "knowledge": knowledge,
                "extractors_path": str(extractors) if extractors.exists() else None,
            }
    return None


def load_extractors(extractors_path: str):
    spec = importlib.util.spec_from_file_location("pack_extractors", extractors_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
