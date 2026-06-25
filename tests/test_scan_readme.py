import unittest

from engine import scan


class ReadmeCmdTest(unittest.TestCase):
    def test_extracts_run_commands_skips_install(self):
        readme = (
            "Install with pip install numpy\n"
            "Run one event:\n"
            "python ideal.py\n"
            "#python ebe_trento.py collision_sys centrality gpu_id num_of_events\n"
            "python ebe_trento.py pbpb5020 30_40 0 100\n"
            "conda install pyopencl\n"
            "./build/foo input.cfg\n"
        )
        cmds = scan.readme_run_commands(readme)
        self.assertIn("python ideal.py", cmds)
        self.assertTrue(any("ebe_trento.py pbpb5020" in c for c in cmds))
        self.assertFalse(any("pip install" in c for c in cmds))
        self.assertFalse(any("conda install" in c for c in cmds))
        self.assertTrue(any("./build/foo" in c for c in cmds))

    def test_primary_entrypoint_prefers_readme_documented(self):
        entries = [
            {"path": "pyvisc/ebe_ampt.py", "cli_style": "argv",
             "argv_names": ["a", "b", "c"], "reads_config": True},
            {"path": "pyvisc/ebe_trento.py", "cli_style": "argv",
             "argv_names": ["sys", "cent"], "reads_config": True},
        ]
        readme = ["python ebe_trento.py auau200 0_5 0 100"]
        p = scan.primary_entrypoint(entries, readme)
        # ebe_ampt has more args but ebe_trento is documented in the README -> preferred
        self.assertEqual(p["path"], "pyvisc/ebe_trento.py")


if __name__ == "__main__":
    unittest.main()
