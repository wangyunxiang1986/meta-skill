import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENGINE_DIR = ROOT / "engine"
PACKS_DIR = ROOT / "packs"

# Curated model-specific tokens that are NOT themselves pack directory names
# (internal file names, parameter names, sub-engine names a model leaks).
CURATED = [
    "pyvisc", "hydro.info", "eos_type", "etaos", "hypersf",
    "optical_glauber_ini", "sampler", "smash", "urqmd", "trento",
]

# Text assets the engine can carry; a model token hidden in any of these
# breaks model-agnosticism just as surely as one in a .py file.
SCANNED_SUFFIXES = {
    ".py", ".json", ".yaml", ".yml", ".txt", ".md",
    ".cl", ".c", ".cpp", ".h", ".sh", ".cfg", ".ini", ".toml",
}


def pack_names():
    """Model names that have a pack — derived, so the guard can't drift
    behind a newly added pack (the bug that let `lbt` slip the blocklist)."""
    return [p.name for p in PACKS_DIR.iterdir()
            if p.is_dir() and not p.name.startswith(("_", "."))]


def forbidden_tokens():
    return sorted(set(CURATED) | set(pack_names()))


def engine_text_files():
    for path in ENGINE_DIR.rglob("*"):
        if path.is_file() and path.suffix in SCANNED_SUFFIXES \
                and "__pycache__" not in path.parts:
            yield path


class EngineBoundaryTest(unittest.TestCase):
    def test_forbidden_covers_every_pack(self):
        """Every pack's model name must be a forbidden engine token; otherwise
        the engine could hardcode that model and the guard below would pass."""
        forbidden = set(forbidden_tokens())
        missing = [n for n in pack_names() if n not in forbidden]
        self.assertEqual(missing, [], f"pack names not in FORBIDDEN: {missing}")

    def test_engine_has_no_model_knowledge(self):
        forbidden = forbidden_tokens()
        offenders = []
        for path in engine_text_files():
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for token in forbidden:
                if re.search(r"\b" + re.escape(token) + r"\b", text):
                    offenders.append(f"{path.relative_to(ENGINE_DIR)}: {token}")
        self.assertEqual(offenders, [], f"engine contains model-specific tokens: {offenders}")

    def test_engine_does_not_import_packs(self):
        offenders = []
        for path in engine_text_files():
            if path.suffix != ".py":
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            # static `import packs` / `from packs`, plus dynamic indirection
            # (`import_module("packs")`, `__import__('packs')`).
            if re.search(r"(^|\n)\s*(import|from)\s+packs\b", text) or \
               re.search(r"(import_module|__import__)\s*\(\s*['\"]packs", text):
                offenders.append(str(path.relative_to(ENGINE_DIR)))
        self.assertEqual(offenders, [], f"engine must not import packs: {offenders}")


if __name__ == "__main__":
    unittest.main()
