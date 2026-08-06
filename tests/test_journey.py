import os
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
            env["GROWTH_LOOP_SKILL_ROOTS"] = os.pathsep.join([str(self.skills), str(link_root / "alias")])
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



class TestJourneyRobustness(unittest.TestCase):
    """Cases the original suite left uncovered, each pinning a real fix."""

    def setUp(self):
        self.skills = tmpdir()
        self.home = tmpdir()
        self.env = {"GROWTH_LOOP_SKILL_ROOTS": str(self.skills),
                    "GROWTH_LOOP_HOME": str(self.home)}

    def tearDown(self):
        shutil.rmtree(self.skills, ignore_errors=True)
        shutil.rmtree(self.home, ignore_errors=True)

    def test_indented_description_is_found(self):
        # description_of() matched at column 0 only, so an indented
        # frontmatter key reported "(no description)" on a skill that has one.
        path = self.skills / "indented" / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("---\n  name: indented\n  description: Indented but real\n---\n\nBody.\n",
                        encoding="utf-8")
        code, out, _ = run("gl-journey", [], env=self.env)
        self.assertEqual(code, 0)
        self.assertIn("Indented but real", out)
        self.assertNotIn("(no description)", out)

    def test_long_description_is_truncated_with_a_marker(self):
        write_skill(self.skills / "verbose" / "SKILL.md", "x" * 200)
        code, out, _ = run("gl-journey", [], env=self.env)
        self.assertEqual(code, 0)
        line = [l for l in out.splitlines() if "verbose" in l][0]
        self.assertIn("...", line)
        self.assertLess(len(line), 160)

    def test_paths_reports_both_resolved_targets(self):
        code, out, _ = run("gl-journey", ["--paths"], env=self.env)
        self.assertEqual(code, 0)
        self.assertIn("skills-root: %s" % self.skills, out)
        self.assertIn("profile: %s" % (self.home / "profile.md"), out)

    def test_paths_falls_back_when_no_override_is_set(self):
        code, out, _ = run("gl-journey", ["--paths"], env={})
        self.assertEqual(code, 0)
        self.assertIn("/.claude/skills", out)
        self.assertIn("/.claude/growth-loop/profile.md", out)

    def test_long_skill_name_is_clipped_to_keep_columns_aligned(self):
        # %-28s does not truncate, so a longer name pushed the age and
        # description columns out of line and the listing stopped being a
        # table.
        long_name = "reindex-search-after-schema-change"
        write_skill(self.skills / long_name / "SKILL.md", "Rebuilds the index")
        write_skill(self.skills / "short" / "SKILL.md", "Short one")
        code, out, _ = run("gl-journey", [], env=self.env)
        self.assertEqual(code, 0)
        rows = [l for l in out.splitlines() if l.endswith(("Rebuilds the index", "Short one"))]
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({r.index("d  ") for r in rows}), 1,
                         "age column is not aligned across rows:\n%s" % "\n".join(rows))

    def test_closing_prompt_claims_no_invocation_data(self):
        # Nothing tracks how often a skill ran - the ledger counts nudges.
        # The closing line must not invite an inference off data absent here.
        _, out, _ = run("gl-journey", [], env=self.env)
        self.assertNotIn("never been invoked", out)
        self.assertIn("do not read the ledger count as usage", out)

if __name__ == "__main__":
    unittest.main()
