import os
import shutil
import unittest

from fixtures import clean_env, load_script, run, tmpdir, write_skill


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

    def test_empty_home_is_not_treated_as_an_override(self):
        # os.environ.get returns "" for a set-but-empty var rather than the
        # default, and Path("") is Path("."), so `export GROWTH_LOOP_HOME=`
        # resolved profile.md to a bare relative path — dropping it into
        # whatever repository happened to be the working directory.
        code, out, _ = run("gl-journey", ["--paths"], env={"GROWTH_LOOP_HOME": ""})
        self.assertEqual(code, 0)
        profile = [l for l in out.splitlines() if l.startswith("profile:")][0]
        self.assertNotEqual(profile.strip(), "profile: profile.md")
        self.assertIn("/.claude/growth-loop/profile.md", profile)

    def test_separator_only_roots_still_resolve_to_a_scanned_root(self):
        # An override of nothing but separators filtered down to no roots,
        # and --paths then named a write target collect_skills() never
        # scanned - the exact desync the resolution exists to prevent.
        # The old --paths branch had its own inline fallback, so asserting
        # on --paths alone passed against the defect. What was broken is that
        # collect_skills() scanned nothing while --paths named a root, so
        # plant a skill in the fallback root's place and assert the sweep
        # actually reads the root --paths reports.
        env = {"GROWTH_LOOP_SKILL_ROOTS": os.pathsep, "GROWTH_LOOP_HOME": str(self.home)}
        code, out, err = run("gl-journey", ["--paths"], env=env)
        self.assertEqual(code, 0, err)
        reported = [l for l in out.splitlines()
                    if l.startswith("skills-root:")][0].split(":", 1)[1].strip()
        code, listing, _ = run("gl-journey", ["--locate", "anything-at-all"], env=env)
        self.assertEqual(code, 1)
        self.assertIn(reported, listing,
                      "the sweep does not read the root --paths reports")

    def test_locate_prints_the_directory_that_gets_deleted(self):
        # forget deletes the whole <slug>/ tree including supporting files.
        # Printing only SKILL.md would show the user less than gets removed.
        write_skill(self.skills / "findable" / "SKILL.md", "A findable skill")
        (self.skills / "findable" / "reference.md").write_text("x", encoding="utf-8")
        code, out, _ = run("gl-journey", ["--locate", "findable"], env=self.env)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), str(self.skills / "findable"))

    def test_locate_reports_a_miss_without_inventing_a_path(self):
        code, out, _ = run("gl-journey", ["--locate", "absent-skill"], env=self.env)
        self.assertEqual(code, 1, "a miss must be distinguishable by status")
        self.assertIn("no skill named", out)
        self.assertNotIn("absent-skill/SKILL.md", out)

    def test_locate_accepts_the_clipped_name_the_listing_prints(self):
        # The listing clips at NAME_CHARS, and forget is told to match
        # against that listing. Requiring the full name here would make any
        # skill with a longer name unreachable from the only view naming it.
        long_name = "reindex-search-after-schema-change"
        write_skill(self.skills / long_name / "SKILL.md", "Long-named skill")
        _, listing, _ = run("gl-journey", [], env=self.env)
        shown = [l for l in listing.splitlines() if "reindex" in l][0]
        clipped = shown.strip().split()[0]
        self.assertTrue(clipped.endswith("..."), clipped)
        code, out, _ = run("gl-journey", ["--locate", clipped], env=self.env)
        self.assertEqual(code, 0, "the clipped name from the listing did not resolve")
        self.assertEqual(out.strip(), str(self.skills / long_name))

    def test_locate_does_not_resolve_a_bare_prefix(self):
        # Prefix matching exists only so the clipped name from the listing
        # resolves. Applied to any query, `--locate deploy` would return
        # deploy-staging, sail past the miss branch, and reach forget's
        # Show step looking like a verified hit.
        write_skill(self.skills / "deploy-staging" / "SKILL.md", "Deploys")
        code, out, _ = run("gl-journey", ["--locate", "deploy"], env=self.env)
        self.assertEqual(code, 1, out)
        self.assertIn("no skill named", out)
        code, out, _ = run("gl-journey", ["--locate", "..."], env=self.env)
        self.assertEqual(code, 1, "a query of only dots must not match everything")

    def test_locate_shows_every_match_rather_than_picking(self):
        write_skill(self.skills / "dup-name" / "SKILL.md", "One")
        second = tmpdir()
        try:
            write_skill(second / "dup-name" / "SKILL.md", "Two")
            env = dict(self.env)
            env["GROWTH_LOOP_SKILL_ROOTS"] = os.pathsep.join(
                [str(self.skills), str(second)])
            code, out, _ = run("gl-journey", ["--locate", "dup-name"], env=env)
            self.assertEqual(code, 0)
            self.assertEqual(len(out.strip().splitlines()), 2, out)
        finally:
            shutil.rmtree(second, ignore_errors=True)

    def test_load_script_ignores_the_ambient_environment(self):
        # Functions imported in-process read os.environ at call time, so an
        # exported GROWTH_LOOP_HOME would silently steer them the way it
        # once steered run(). Nothing loaded today reads it; this pins the
        # sanitising before something does.
        home = load_script("gl-journey").home
        os.environ["GROWTH_LOOP_HOME"] = "/definitely/not/this/one"
        try:
            with clean_env():
                resolved = str(home())
        finally:
            os.environ.pop("GROWTH_LOOP_HOME", None)
        self.assertNotIn("/definitely/not/this/one", resolved)
        self.assertTrue(resolved.endswith("/.claude/growth-loop"), resolved)

    def test_stale_filters_skills_only_not_memory_or_ledger(self):
        # Both the --stale help text and journey/SKILL.md assert this, and a
        # live session had already misread a memory file as a stale item
        # before the skill said so. Nothing pinned it: dropping MEMORY and
        # LEDGER from the filtered pass left the suite green.
        write_skill(self.skills / "recent" / "SKILL.md", "Written today")
        _, out, _ = run("gl-journey", ["--stale", "60"], env=self.env)
        self.assertIn("(none)", out, "the skill should have been filtered out")
        for section in ("MEMORY", "LEDGER"):
            self.assertIn(section, out,
                          "%s must print in full on a filtered pass" % section)
        self.assertIn("nudge(s) recorded", out)


class TestJourneyDuplicates(unittest.TestCase):
    """--duplicates: a scalable first pass over descriptions.

    The manual eyeball-every-pair audit in journey/SKILL.md does not scale
    past a handful of skills. This flag surfaces a similarity-ranked
    shortlist so the model reads two files, not the whole set, before
    deciding anything - it never decides a merge by itself.
    """

    def setUp(self):
        self.skills = tmpdir()
        self.home = tmpdir()
        self.env = {"GROWTH_LOOP_SKILL_ROOTS": str(self.skills),
                    "GROWTH_LOOP_HOME": str(self.home)}

    def tearDown(self):
        shutil.rmtree(self.skills, ignore_errors=True)
        shutil.rmtree(self.home, ignore_errors=True)

    def test_flags_near_identical_descriptions_as_a_pair(self):
        write_skill(self.skills / "deploy-staging" / "SKILL.md",
                    "Deploy the app to the staging cluster with zero downtime")
        write_skill(self.skills / "staging-deploy" / "SKILL.md",
                    "Deploy the app to the staging cluster with zero downtime, twice")
        code, out, _ = run("gl-journey", ["--duplicates"], env=self.env)
        self.assertEqual(code, 0)
        self.assertIn("deploy-staging", out)
        self.assertIn("staging-deploy", out)

    def test_omits_pairs_below_the_default_threshold(self):
        write_skill(self.skills / "deploy-staging" / "SKILL.md",
                    "Deploy the app to the staging cluster")
        write_skill(self.skills / "rotate-logs" / "SKILL.md",
                    "Compress and archive old log files nightly")
        code, out, _ = run("gl-journey", ["--duplicates"], env=self.env)
        self.assertEqual(code, 0)
        self.assertIn("(none)", out)

    def test_threshold_flag_widens_or_narrows_the_shortlist(self):
        write_skill(self.skills / "deploy-staging" / "SKILL.md",
                    "Deploy the app to staging")
        write_skill(self.skills / "deploy-prod" / "SKILL.md",
                    "Publish the release to production")
        code, loose, _ = run("gl-journey", ["--duplicates", "--threshold", "0.2"],
                             env=self.env)
        self.assertEqual(code, 0)
        self.assertIn("deploy-staging", loose)
        self.assertIn("deploy-prod", loose)
        code, strict, _ = run("gl-journey", ["--duplicates", "--threshold", "0.95"],
                              env=self.env)
        self.assertEqual(code, 0)
        self.assertIn("(none)", strict)

    def test_only_one_skill_never_crashes(self):
        write_skill(self.skills / "lonely" / "SKILL.md", "The only skill here")
        code, out, _ = run("gl-journey", ["--duplicates"], env=self.env)
        self.assertEqual(code, 0)
        self.assertIn("(none)", out)


if __name__ == "__main__":
    unittest.main()
