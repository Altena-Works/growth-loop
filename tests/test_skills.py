import unittest

from fixtures import MODEL_INVOKED, PLUGIN_ROOT, USER_INVOKED_ONLY

DESCRIPTION_CAP = 1536      # verified 2026-08-04: description + when_to_use cap
BODY_LINE_CAP = 500
HEDGE_WORDS = ("might work", "probably works", "may or may not", "should be fine")


def parse_frontmatter(path):
    """Return (frontmatter dict, body). Flat key: value YAML only."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines and lines[0].strip() == "---", "%s has no frontmatter" % path
    meta, end = {}, None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = index
            break
        if ":" in line and not line.startswith((" ", "\t", "-")):
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip("\"'")
    assert end is not None, "%s frontmatter is unterminated" % path
    return meta, "\n".join(lines[end + 1:])


def existing_skills():
    return sorted((PLUGIN_ROOT / "skills").glob("*/SKILL.md"))


class TestSkillFrontmatter(unittest.TestCase):
    def test_every_skill_has_name_and_description(self):
        for path in existing_skills():
            meta, _ = parse_frontmatter(path)
            self.assertEqual(meta.get("name"), path.parent.name, path)
            self.assertTrue(meta.get("description"), path)

    def test_description_within_cap(self):
        for path in existing_skills():
            meta, _ = parse_frontmatter(path)
            combined = meta.get("description", "") + meta.get("when_to_use", "")
            self.assertLessEqual(len(combined), DESCRIPTION_CAP, path)

    def test_description_states_when_not_just_what(self):
        # A description without a trigger clause cannot be selected on.
        for path in existing_skills():
            meta, _ = parse_frontmatter(path)
            text = (meta.get("description", "") + " " + meta.get("when_to_use", "")).lower()
            self.assertTrue(any(w in text for w in ("when ", "after ", "the moment")),
                            "%s description names no trigger situation" % path)

    def test_invocation_flags(self):
        for name in USER_INVOKED_ONLY:
            path = PLUGIN_ROOT / "skills" / name / "SKILL.md"
            if not path.exists():
                continue
            meta, _ = parse_frontmatter(path)
            self.assertEqual(meta.get("disable-model-invocation"), "true",
                             "%s: review and deletion are human decisions" % name)
        for name in MODEL_INVOKED:
            path = PLUGIN_ROOT / "skills" / name / "SKILL.md"
            if not path.exists():
                continue
            meta, _ = parse_frontmatter(path)
            self.assertNotIn("disable-model-invocation", meta, name)

    def test_body_length(self):
        for path in existing_skills():
            _, body = parse_frontmatter(path)
            self.assertLess(len(body.splitlines()), BODY_LINE_CAP, path)

    def test_no_hedging(self):
        for path in existing_skills():
            _, body = parse_frontmatter(path)
            for hedge in HEDGE_WORDS:
                self.assertNotIn(hedge, body.lower(), "%s hedges: %r" % (path, hedge))

    def test_declining_is_a_first_class_outcome(self):
        for name in ("learn", "refine", "profile"):
            path = PLUGIN_ROOT / "skills" / name / "SKILL.md"
            if not path.exists():
                continue
            _, body = parse_frontmatter(path)
            self.assertIn("## When to write nothing", body,
                          "%s must make declining first-class" % name)


class TestLearn(unittest.TestCase):
    def setUp(self):
        self.path = PLUGIN_ROOT / "skills" / "learn" / "SKILL.md"
        self.meta, self.body = parse_frontmatter(self.path)

    def test_runs_journey_first_and_routes_to_refine_on_overlap(self):
        # Bare `gl-journey` is not on the Bash tool's PATH inside a plugin
        # skill (measured empirically) - it must be invoked by explicit
        # path so the assertion has to pin that form, not just the substring.
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey', self.body)
        self.assertIn("/growth-loop:refine", self.body)

    def test_states_the_three_way_gate(self):
        for gate in ("took real work", "will recur", "procedural"):
            self.assertIn(gate, self.body)

    def test_carries_the_output_template(self):
        for heading in ("When this applies", "The approach", "What goes wrong"):
            self.assertIn(heading, self.body)

    def test_resolves_the_write_target_instead_of_hardcoding_it(self):
        # learn must write into the first root gl-journey scans. Hardcoding
        # ~/.claude/skills desynchronises the two the moment anyone sets
        # GROWTH_LOOP_SKILL_ROOTS: learn keeps writing where gl-journey no
        # longer reads, so learn's own overlap check — the thing that stops
        # near-duplicates — silently stops finding anything.
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey --paths', self.body)
        self.assertIn("skills-root:", self.body)

    def test_does_not_instruct_a_hardcoded_skills_path(self):
        self.assertNotIn("`~/.claude/skills/<slug>/SKILL.md`", self.body)

    def test_offers_the_subagent(self):
        self.assertIn("skill-author", self.body)

    def test_takes_arguments(self):
        self.assertIn("$ARGUMENTS", self.body)


class TestRefine(unittest.TestCase):
    def setUp(self):
        self.meta, self.body = parse_frontmatter(
            PLUGIN_ROOT / "skills" / "refine" / "SKILL.md")

    def test_requires_reading_the_whole_file_first(self):
        self.assertIn("Read the whole file", self.body)

    def test_requires_a_dated_revisions_entry(self):
        self.assertIn("## Revisions", self.body)

    def test_routes_to_forget_when_beyond_repair(self):
        self.assertIn("/growth-loop:forget", self.body)
        self.assertIn("beyond repair", self.body)

    def test_fires_only_on_something_that_happened_this_session(self):
        self.assertIn("this session", self.body)


class TestSkillAuthorAgent(unittest.TestCase):
    def setUp(self):
        self.meta, self.body = parse_frontmatter(
            PLUGIN_ROOT / "agents" / "skill-author.md")

    def test_frontmatter_fields(self):
        self.assertEqual(self.meta.get("name"), "skill-author")
        self.assertTrue(self.meta.get("description"))
        self.assertEqual(self.meta.get("tools"), "Read, Write, Edit, Glob, Grep, Bash")

    def test_reports_exactly_two_things(self):
        self.assertIn("exactly two things", self.body)

    def test_refuses_dead_end_free_skills(self):
        self.assertIn("What goes wrong", self.body)

    def test_carries_the_same_template_learn_uses(self):
        # skill-author is the delegated path for the job learn does inline.
        # It mandated only "What goes wrong", so a delegated skill came out
        # with different headings than an inline one - measured in a live
        # dispatch, which produced "The command" and "Read this before you
        # run anything" instead. Two shapes in one library is unskimmable,
        # and journey's duplicate hunt compares these sections directly.
        learn_body = parse_frontmatter(
            PLUGIN_ROOT / "skills" / "learn" / "SKILL.md")[1]
        for heading in ("## When this applies", "## The approach",
                        "## What goes wrong"):
            self.assertIn(heading, learn_body, "learn lost %s" % heading)
            self.assertIn(heading, self.body,
                          "skill-author does not mandate %s" % heading)


class TestRecall(unittest.TestCase):
    def setUp(self):
        self.meta, self.body = parse_frontmatter(
            PLUGIN_ROOT / "skills" / "recall" / "SKILL.md")

    def test_runs_gl_recall(self):
        # Explicit path required - bare `gl-recall` is not on PATH inside a
        # plugin skill (measured empirically); see recall/SKILL.md.
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}"/bin/gl-recall', self.body)

    def test_teaches_reading_the_hits(self):
        for cue in ("newest session first", "resolution", "decided"):
            self.assertIn(cue, self.body)

    def test_never_dumps_raw_output(self):
        self.assertIn("conclusion first", self.body.lower())

    def test_empty_state_directs_to_the_env_var(self):
        self.assertIn("CLAUDE_TRANSCRIPT_DIR", self.body)

    def test_closes_the_loop_to_persistence(self):
        self.assertIn("searched twice", self.body)


class TestProfile(unittest.TestCase):
    def setUp(self):
        self.meta, self.body = parse_frontmatter(
            PLUGIN_ROOT / "skills" / "profile" / "SKILL.md")

    def test_resolves_the_file_path_instead_of_hardcoding_it(self):
        # A live session proved the earlier prose form ("~/.claude/... , or
        # $GROWTH_LOOP_HOME/... when that variable is set") fails: the model
        # took the first path and never consulted the variable, so the write
        # silently never happened. The skill must resolve the path with a
        # command whose output it then uses.
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey --paths', self.body)
        self.assertIn("profile:", self.body)

    def test_does_not_instruct_a_hardcoded_profile_path(self):
        self.assertNotIn("`~/.claude/growth-loop/profile.md`", self.body)

    def test_has_the_three_sections(self):
        for section in ("Tooling", "Conventions", "Working style"):
            self.assertIn(section, self.body)

    def test_states_the_three_month_test(self):
        self.assertIn("three months", self.body)

    def test_states_the_second_occurrence_rule(self):
        self.assertIn("second occurrence", self.body)

    def test_states_the_line_cap(self):
        self.assertIn("60 lines", self.body)

    def test_carries_the_privacy_exclusions(self):
        for excluded in ("health", "finances", "relationships", "politics", "inferred"):
            self.assertIn(excluded, self.body.lower())

    def test_refuses_honesty_degrading_instructions(self):
        self.assertIn("less honest", self.body)

    def test_never_announces_the_write(self):
        self.assertIn("Never announce", self.body)


class TestJourneySkill(unittest.TestCase):
    def setUp(self):
        self.meta, self.body = parse_frontmatter(
            PLUGIN_ROOT / "skills" / "journey" / "SKILL.md")

    def test_is_user_invoked_only(self):
        self.assertEqual(self.meta.get("disable-model-invocation"), "true")

    def test_runs_both_journey_invocations(self):
        # Explicit path required - bare `gl-journey` is not on PATH inside a
        # plugin skill (measured empirically).
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey', self.body)
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey --stale 60', self.body)

    def test_forces_a_three_way_verdict(self):
        for verdict in ("delete", "verify", "keep"):
            self.assertIn(verdict, self.body.lower())
        self.assertIn("no undecided leftovers", self.body.lower())

    def test_audits_the_description_set(self):
        self.assertIn("would exactly the right one fire", self.body)

    def test_reports_a_verdict_not_the_inventory(self):
        self.assertIn("not the inventory", self.body)


class TestForget(unittest.TestCase):
    def setUp(self):
        self.meta, self.body = parse_frontmatter(
            PLUGIN_ROOT / "skills" / "forget" / "SKILL.md")

    def test_is_user_invoked_only(self):
        self.assertEqual(self.meta.get("disable-model-invocation"), "true")

    def test_requires_confirmation_before_deleting(self):
        self.assertIn("Wait for confirmation", self.body)

    def test_forbids_tombstones(self):
        self.assertIn("Delete, do not soften", self.body)
        self.assertIn("deprecated", self.body)

    def test_deletes_the_whole_directory(self):
        self.assertIn("<slug>/", self.body)

    def test_removes_derived_entries(self):
        self.assertIn("derived", self.body)

    def test_asks_first_on_ambiguous_scope(self):
        self.assertIn("ambiguous", self.body.lower())

    def test_locates_via_explicit_journey_path(self):
        # Explicit path required - bare `gl-journey` is not on PATH inside a
        # plugin skill (measured empirically).
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey', self.body)


class TestScriptInvocationAllowedTools(unittest.TestCase):
    """The four skills that shell out to a bin/ script must pin an
    allowed-tools rule on the same ${CLAUDE_PLUGIN_ROOT} path they invoke in
    the body, or every invocation stops for a permission prompt."""

    CASES = {
        "learn": "gl-journey",
        "recall": "gl-recall",
        "journey": "gl-journey",
        "forget": "gl-journey",
        "profile": "gl-journey",
    }

    def test_allowed_tools_matches_the_invoked_path(self):
        for name, script in self.CASES.items():
            path = PLUGIN_ROOT / "skills" / name / "SKILL.md"
            meta, _ = parse_frontmatter(path)
            allowed = meta.get("allowed-tools", "")
            self.assertIn('"${CLAUDE_PLUGIN_ROOT}"/bin/%s' % script, allowed,
                          "%s: allowed-tools does not cover %s" % (name, script))


if __name__ == "__main__":
    unittest.main()
