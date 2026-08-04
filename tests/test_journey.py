import shutil
import unittest

from fixtures import run, tmpdir, write_skill


class TestJourney(unittest.TestCase):
    def setUp(self):
        self.skills = tmpdir()
        self.home = tmpdir()
        write_skill(self.skills / "fresh-thing" / "SKILL.md",
                    "Rebuild the search index after a schema change", age_days=2)
        write_skill(self.skills / "old-thing" / "SKILL.md",
                    "Deploy to the retired staging cluster", age_days=200)
        (self.home / "ledger.jsonl").write_text('{"ts": 1, "session": "a"}\n',
                                                encoding="utf-8")
        (self.home / "profile.md").write_text("# Profile\n\n- uses pnpm (2026-08-01)\n",
                                              encoding="utf-8")
        self.env = {"GROWTH_LOOP_SKILL_ROOTS": str(self.skills),
                    "GROWTH_LOOP_HOME": str(self.home)}

    def tearDown(self):
        shutil.rmtree(self.skills, ignore_errors=True)
        shutil.rmtree(self.home, ignore_errors=True)

    def test_lists_skills_with_descriptions_and_age(self):
        code, out, _ = run("gl-journey", [], env=self.env)
        self.assertEqual(code, 0)
        self.assertIn("fresh-thing", out)
        self.assertIn("Rebuild the search index after a schema change", out)
        self.assertIn("2d", out)

    def test_flags_stale_skills(self):
        _, out, _ = run("gl-journey", [], env=self.env)
        stale_line = [l for l in out.splitlines() if "old-thing" in l][0]
        self.assertIn("STALE", stale_line)
        fresh_line = [l for l in out.splitlines() if "fresh-thing" in l][0]
        self.assertNotIn("STALE", fresh_line)

    def test_stale_flag_filters(self):
        _, out, _ = run("gl-journey", ["--stale", "60"], env=self.env)
        self.assertIn("old-thing", out)
        self.assertNotIn("fresh-thing", out)

    def test_reports_memory_files_and_ledger_count(self):
        _, out, _ = run("gl-journey", [], env=self.env)
        self.assertIn("profile.md", out)
        self.assertIn("LEDGER", out)
        self.assertIn("1 nudge", out)

    def test_dedupes_by_resolved_path(self):
        link_root = tmpdir()
        try:
            (link_root / "alias").symlink_to(self.skills)
            env = dict(self.env)
            env["GROWTH_LOOP_SKILL_ROOTS"] = "%s:%s" % (self.skills, link_root / "alias")
            _, out, _ = run("gl-journey", [], env=env)
            self.assertEqual(out.count("fresh-thing"), 1)
        finally:
            shutil.rmtree(link_root, ignore_errors=True)

    def test_closes_with_the_review_prompt(self):
        _, out, _ = run("gl-journey", [], env=self.env)
        self.assertIn("finished work to delete", out)
        self.assertIn("drifted knowledge to re-verify", out)

    def test_missing_roots_do_not_crash(self):
        code, out, err = run("gl-journey", [],
                             env={"GROWTH_LOOP_SKILL_ROOTS": "/no/such/dir",
                                  "GROWTH_LOOP_HOME": "/no/such/home"})
        self.assertEqual(code, 0)
        self.assertEqual(err.strip(), "")
        self.assertIn("SKILLS", out)


if __name__ == "__main__":
    unittest.main()
