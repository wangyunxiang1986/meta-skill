import pathlib
import re
import unittest

ENGINE_DIR = pathlib.Path(__file__).resolve().parents[1] / "engine"

FORBIDDEN = [
    "clvisc", "pyvisc", "hydro.info", "eos_type", "etaos", "hypersf",
    "optical_glauber_ini", "sampler", "smash", "urqmd", "trento",
]


class EngineBoundaryTest(unittest.TestCase):
    def test_engine_has_no_model_knowledge(self):
        offenders = []
        for path in ENGINE_DIR.rglob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            for token in FORBIDDEN:
                if re.search(r"\b" + re.escape(token) + r"\b", text):
                    offenders.append(f"{path.relative_to(ENGINE_DIR)}: {token}")
        self.assertEqual(offenders, [], f"engine contains model-specific tokens: {offenders}")

    def test_engine_does_not_import_packs(self):
        offenders = []
        for path in ENGINE_DIR.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if re.search(r"(^|\n)\s*(import|from)\s+packs\b", text):
                offenders.append(str(path.relative_to(ENGINE_DIR)))
        self.assertEqual(offenders, [], f"engine must not import packs: {offenders}")


if __name__ == "__main__":
    unittest.main()
