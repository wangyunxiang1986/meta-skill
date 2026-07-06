"""The auto-candidate milestone: a skill built ONLY from automatically-obtainable
information (structural scan + grounding on a real output header, no physics priors)
runs end-to-end to T2. Uses a tiny synthetic program that writes '# key = value'
headers, so it needs no real physics code and runs in CI.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]

# a minimal prebuilt "binary" (executable script) that writes N event files, each with a
# '# mult = <n>' header + a grid row. Mirrors the real TRENTo case: a ./prog invocation
# whose binary derive_demo stages into the work dir (not a relative source path).
FAKE_PROG = '''\
#!/usr/bin/env python3
import os, sys
outdir = sys.argv[sys.argv.index("-o") + 1] if "-o" in sys.argv else "."
os.makedirs(outdir, exist_ok=True)
for i in range(3):
    with open(os.path.join(outdir, "%d.dat" % i), "w") as f:
        f.write("# event %d\\n# b = %.1f\\n# mult = %d\\n" % (i, i * 1.5, 10 + i * 10))
        f.write("1 2 3\\n4 5 6\\n")
print("done")
'''


class DeriveDemoTest(unittest.TestCase):
    def test_auto_candidate_reaches_t2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "proj"
            (root / "src").mkdir(parents=True)
            (root / "build").mkdir()
            (root / ".git").mkdir()
            # a scannable source entry (for primary_entry) ...
            (root / "src" / "gen.cxx").write_text(
                "int main(int argc, char** argv){ return 0; }\n", encoding="utf-8")
            # ... and the prebuilt executable the command invokes as ./fakeprog
            exe = root / "build" / "fakeprog"
            exe.write_text(FAKE_PROG, encoding="utf-8")
            exe.chmod(0o755)
            (root / "README.md").write_text("# fake\n", encoding="utf-8")
            work = pathlib.Path(tmp) / "work"
            command = ["./fakeprog", "-o", "{work}/out"]
            proc = subprocess.run(
                [sys.executable, "-m", "drafting.derive_demo",
                 "--project-root", str(root),
                 "--command", json.dumps(command),
                 "--tier1-output", "0.dat",
                 "--work-dir", str(work)],
                cwd=str(REPO), capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            r = json.loads(proc.stdout)
            auto = r["auto_candidate"]["auto_derived"]
            # observables auto-discovered from the real header, no priors
            self.assertIn("mult", auto["observables_from_header"])
            self.assertEqual(auto["tier2_observable"], "mult")
            # and the skill actually ran to T2 on those alone
            self.assertEqual(r["run"]["tier_reached"], 2)
            self.assertEqual(r["run"]["blockers"], [])
            self.assertAlmostEqual(r["run"]["observable"]["values"]["mean_mult"], 20.0, places=6)


if __name__ == "__main__":
    unittest.main()
