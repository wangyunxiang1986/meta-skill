import pathlib
import unittest

SKILL = pathlib.Path(__file__).resolve().parents[1] / "SKILL.md"


class SkillMdTest(unittest.TestCase):
    def test_structure(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---"))
        self.assertIn("name: project-explorer-and-skill-creator", text)
        for marker in ("three main modules", "six-step loop",
                       "## 1 扫描", "### 1.1 扫源码", "### 1.2 建立项目画像",
                       "## 2 构造 Skill", "### 2.1 生成 version-specific skill",
                       "## 3 测试 Skill", "### 3.1 分层验证",
                       "### 3.2 记录经验", "### 3.3 迭代更新",
                       "engine.scan", "engine.generate", "engine.understanding",
                       "run_launcher", "project-understanding.md",
                       "verification-report.md", "blocked-runs.md",
                       "config.py", "run.py", "analysis.py", "visualize.py"):
            self.assertIn(marker, text)
        for norm in ("non-destructive", "do not silently", "<WORK_DIR>"):
            self.assertIn(norm, text)
        self.assertIn("loop back to module 2", text)
        self.assertNotIn("loop back to step 2", text)


if __name__ == "__main__":
    unittest.main()
