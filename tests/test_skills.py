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


def flat(text):
    """Collapse wrapping so an assertion does not depend on line breaks.

    These files are hand-wrapped prose. Asserting on a phrase that happens
    to straddle a newline fails for a reason that has nothing to do with
    the requirement, and — worse — quietly passes when the phrase is
    reworded around the break. Normalise, then assert on meaning.
    """
    return " ".join(text.split())


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
        # A bare "when" passes on any prose - deleting learn's entire "Use
        # when the user says ..." clause left this green because an
        # incidental "when" survived elsewhere in the sentence. Require the
        # clause that actually names triggering situations.
        for path in existing_skills():
            meta, _ = parse_frontmatter(path)
            text = (meta.get("description", "") + " " + meta.get("when_to_use", ""))
            self.assertTrue(any(c in text for c in ("Use when", "Run this", "use when")),
                            "%s description has no explicit trigger clause" % path)

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

    def test_refuses_to_overwrite_an_existing_skill(self):
        # learn is model-invocable and writes a whole file. Without this,
        # a slug collision destroys a skill silently - the one path where a
        # model-invoked skill could do what forget requires confirmation for.
        self.assertIn("Check the target does not already exist before writing",
                      flat(self.body))
        self.assertIn("Do not overwrite it", flat(self.body))

    def test_does_not_instruct_a_hardcoded_skills_path(self):
        # Pinning one backticked spelling let the same defect back in under
        # any other quoting - and did, in profile's frontmatter, while the
        # equivalent test stayed green. Check the whole file, unquoted.
        text = self.path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.lstrip().startswith(("#", ">")) or "hardcoded" in line:
                continue
            self.assertNotIn("~/.claude/skills/<slug>", line, line)

    def test_offers_the_subagent(self):
        self.assertIn("skill-author", self.body)

    def test_hands_the_subagent_the_results_of_both_write_checks(self):
        # skill-author cannot repeat them: no ${CLAUDE_PLUGIN_ROOT}, so no
        # --paths and no existence check. Delegation fires on a long session,
        # which is exactly when the resolved path has fallen out of view.
        index = self.body.index("## Delegating")
        section = self.body[index:]
        self.assertIn("hand over their results", flat(section))
        self.assertIn("resolved absolute path", flat(section))
        self.assertIn("confirm that path is free", flat(section))

    def test_grants_only_the_script_it_actually_runs(self):
        # It carried Bash(echo:*) and Bash(cut:*) left over from a removed
        # shell-expansion form. Every other grant here pins one exact script.
        allowed = self.meta.get("allowed-tools", "")
        self.assertIn("gl-journey", allowed)
        for stray in ("echo", "cut"):
            self.assertNotIn("Bash(%s:" % stray, allowed)

    def test_takes_arguments(self):
        self.assertIn("$ARGUMENTS", self.body)
        # The README advertises /growth-loop:learn [dir|url] and names the
        # URL branch as the plugin's one network touch, so both branches
        # have to survive here for that to stay true.
        section = self.body[self.body.index("## Handling $ARGUMENTS"):]
        self.assertIn("a directory", section)
        self.assertIn("a URL", section)

    def test_promotes_pending_jots_through_the_same_gate(self):
        # jot queues raw, ungated notes. Something has to run learn's own
        # checks over them before one becomes a skill, or the gate above is
        # decorative for anything that arrived via jot instead of directly.
        index = self.body.index("## Pending jots")
        section = flat(self.body[index:])
        self.assertIn("candidates:", section)
        self.assertIn("overlap check", section)
        self.assertIn("three-condition gate", section)
        self.assertIn("remove that entry from", section)


class TestJot(unittest.TestCase):
    def setUp(self):
        self.meta, self.body = parse_frontmatter(
            PLUGIN_ROOT / "skills" / "jot" / "SKILL.md")

    def test_resolves_the_queue_path_instead_of_hardcoding_it(self):
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey --paths', self.body)
        self.assertIn("candidates:", self.body)

    def test_does_not_run_learns_gate(self):
        # jot is deliberately lighter than learn: no three-condition gate,
        # no dedup check, no confirmation before writing. Those belong to
        # learn's promotion step, not here - jot says so explicitly rather
        # than silently omitting them.
        flattened = flat(self.body)
        self.assertIn("happen later, at promotion time - not now, and not "
                      "by this skill", flattened)
        self.assertNotIn("Wait for confirmation", flattened)

    def test_does_not_write_a_full_skill_template(self):
        for heading in ("## When this applies", "## The approach",
                        "## What goes wrong"):
            self.assertNotIn(heading, self.body)

    def test_never_blocks_on_confirmation(self):
        self.assertIn("do not ask for confirmation", flat(self.body).lower())


class TestRefine(unittest.TestCase):
    def setUp(self):
        self.meta, self.body = parse_frontmatter(
            PLUGIN_ROOT / "skills" / "refine" / "SKILL.md")

    def test_requires_reading_the_whole_file_first(self):
        self.assertIn("Read the whole file", self.body)

    def test_requires_a_dated_revisions_entry(self):
        # "## Revisions" survives in the code fence, so the heading alone
        # pinned neither the date nor the reason - and the reason is what
        # stops the next reader reinstating the step that was just removed.
        self.assertIn("## Revisions", self.body)
        flattened = flat(self.body)
        self.assertIn("dated entry", flattened)
        self.assertIn("what changed **and why**", flattened)

    def test_routes_to_forget_when_beyond_repair(self):
        self.assertIn("/growth-loop:forget", self.body)
        self.assertIn("beyond repair", self.body)
        # The route is only safe with the gate named: refine is
        # model-invocable and holds Edit, so "route to forget" without this
        # reads as something it may do itself. journey and profile pin the
        # same sentence; refine's copy did not.
        self.assertIn("cannot invoke it", flat(self.body))
        self.assertIn("Do not delete the directory yourself", flat(self.body))

    def test_the_description_admits_review_driven_corrections(self):
        # The description is the gate: it is what a model reads to decide
        # whether to invoke at all, before the body loads. The live failure
        # was a refusal to invoke, so loosening only the body left the fix
        # short of the mechanism that produced the bug.
        description = self.meta["description"]
        self.assertNotIn("never as a retrospective", description)
        self.assertIn("evidence", description)
        self.assertIn("review", description)

    def test_declining_polish_does_not_decline_a_merge(self):
        # "not actually wrong, needs no edit" can fire on the exact case
        # journey routes here: a keeper is not wrong, it is missing what
        # the loser documents.
        index = self.body.index("## When to write nothing")
        # Both inbound routes from journey, not just the merge: the second
        # was added a round later and the carve-out was not extended, which
        # is the same miss this test exists for.
        section = flat(self.body[index:])
        self.assertIn("declines neither route that `/growth-loop:journey` "
                      "sends here", section)
        self.assertIn("narrowing an overlapping description", section)

    def test_accepts_a_review_found_description_overlap(self):
        # journey routes these here; without the trigger and the matching
        # edit rule, refine's own text tells it to do the opposite thing
        # (broaden to name what fired) for a case where nothing fired.
        flattened = flat(self.body)
        self.assertIn("A review found two descriptions that both plausibly "
                      "claim the same task", flattened)
        self.assertIn("**narrow one of them**", flattened)

    def test_fires_on_evidence_not_recency(self):
        # journey routes a duplicate merge here, but the old rule said
        # "only on something that happened this session" - so a live review
        # correctly refused to invoke refine, and the merge had nowhere to
        # go. The standard is evidence in view, which a review meets.
        self.assertIn("this session", self.body)
        self.assertIn("refine on evidence in front of you, never on a hunch",
                      flat(self.body))
        self.assertIn("/growth-loop:journey", self.body)


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
        # "What goes wrong" alone is satisfied by the template block and the
        # section heading, so deleting the whole refusal left this green.
        self.assertIn("What goes wrong", self.body)
        self.assertIn("do not invent one", flat(self.body))
        self.assertIn("do not write the skill anyway", flat(self.body))

    def test_refuses_to_choose_its_own_write_path(self):
        # It has no ${CLAUDE_PLUGIN_ROOT}, so it cannot run gl-journey
        # --paths. Left to pick, the delegated branch writes to a hardcoded
        # root the review never reads - the defect learn had just been fixed
        # for, reintroduced through the subagent.
        self.assertIn("Do not choose a path", flat(self.body))
        self.assertIn("ask for it and write nothing", flat(self.body))

    def test_refuses_to_overwrite_an_existing_file(self):
        self.assertIn("If a file already exists at that path, stop.",
                      flat(self.body))

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
        # "conclusion first" survived deleting the no-dumping rule outright.
        self.assertIn("conclusion first", flat(self.body).lower())
        self.assertIn("Never dump raw", flat(self.body))

    def test_says_to_raise_max_not_just_days_for_an_old_memory(self):
        # --days only moves the cutoff; the search reads newest first and
        # stops at --max, so on a recurring topic the quota fills with
        # recent sessions and the old one is never reached. This skill
        # documented --days alone for a full round after that was measured.
        # A stray mention of --max elsewhere in the section is not the
        # point: the command the reader copies has to carry it.
        self.assertIn('--days 365 --max', flat(self.body))
        self.assertIn("stopped at the --max limit", flat(self.body))

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
        # Same shape as learn's: check the whole file including frontmatter,
        # regardless of quoting. The description is the first path the model
        # reads, so a literal there defeats the body's resolution rule.
        text = (PLUGIN_ROOT / "skills" / "profile" / "SKILL.md").read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.lstrip().startswith(("#", ">")) or "GROWTH_LOOP_HOME:-" in line:
                continue
            self.assertNotIn("~/.claude/growth-loop/profile.md", line, line)

    def test_has_the_three_sections(self):
        for section in ("Tooling", "Conventions", "Working style"):
            self.assertIn(section, self.body)

    def test_states_the_three_month_test(self):
        self.assertIn("three months", self.body)

    def test_states_the_second_occurrence_rule(self):
        self.assertIn("second occurrence", self.body)

    def test_age_out_is_proposal_only(self):
        # The cap used to say "age out the entries that were never
        # reinforced" in a model-invocable skill whose closing rule is not
        # to announce the write - reaching, silently, the effect forget
        # requires showing the line and waiting for a human to reach.
        self.assertIn("Propose those lines. Do not remove them here.",
                      flat(self.body))
        self.assertIn("/growth-loop:forget", self.body)

    def test_routing_to_forget_says_the_model_cannot_invoke_it(self):
        # refine and journey both spell this out where they route to forget.
        # Without it, "route to forget" reads as something the model does.
        index = self.body.index("/growth-loop:forget")
        window = self.body[max(0, index - 400):index + 400]
        self.assertIn("cannot invoke", flat(window))

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
        # Matching bare words let two of the three bullets be deleted with
        # the suite green - "keep" survives in "the keeper now covers
        # ground the loser still claims". The Delete bullet is where
        # journey's gate lives, so it is the one that must not vanish.
        flattened = flat(self.body)
        self.assertIn("**Delete**", flattened)
        self.assertIn("**Verify and correct**", flattened)
        self.assertIn("**Keep and say so**", flattened)
        self.assertIn("a recommendation in the report, not an action you take",
                      flattened)
        self.assertIn("no undecided leftovers", flattened.lower())

    def test_duplicate_merge_does_not_reach_deletion(self):
        # The Delete verdict's "recommendation, not an action" scope covers
        # only items --stale surfaced. Duplicates are found in the full
        # inventory, so a merge instruction whose second half is removing
        # the loser reached deletion around forget entirely.
        index = self.body.index("## Duplicates")
        section = self.body[index:self.body.index("## Audit")]
        self.assertIn("recommend the loser for deletion and stop", flat(section))
        self.assertIn("Do not delete it here", flat(section))
        self.assertIn("cannot call", flat(section))

    def test_audits_the_description_set(self):
        self.assertIn("would exactly the right one fire", self.body)

    def test_report_does_not_promise_deletions_it_cannot_perform(self):
        # Routing to forget is a recommendation, not an action - stated 30
        # lines earlier. The Report section used to ask for "what got
        # deleted", reintroducing the framing the Delete bullet suppresses.
        self.assertNotIn("what got deleted", self.body)
        self.assertIn("recommended for deletion", self.body)

    def test_description_scope_matches_the_body(self):
        # The body was narrowed to "every skill" a round before the
        # description was, and the description is what a model reads first.
        self.assertIn("every stale skill", self.meta["description"])
        self.assertNotIn("each stale item", self.meta["description"])

    def test_verdict_scope_is_skills_not_every_row(self):
        # --stale narrows SKILLS only, so "every item it surfaces" demanded
        # a delete/verify/keep call on CLAUDE.md and the ledger - and "no
        # undecided leftovers" forbade skipping them. A live session had
        # already misread a memory row this way.
        self.assertIn("Every **skill** `gl-journey --stale 60` surfaces",
                      flat(self.body))

    def test_stale_scope_is_stated_where_the_reader_gathers(self):
        # The script's behaviour is pinned in test_journey. This pins the
        # prose that tells the model to expect it.
        self.assertIn("narrows the SKILLS section only", flat(self.body))

    def test_audit_routes_overlaps_but_not_predicted_vagueness(self):
        # An overlap is evidence with both files in view; vagueness is a
        # prediction that nothing has failed on yet, which refine declines
        # by design. Sending both would reintroduce the contract conflict.
        section = flat(self.body[self.body.index("## Audit the description set"):])
        self.assertIn("Route it there and say so in the report", section)
        self.assertIn("do not send it there", section)
        self.assertIn("descriptions routed to refine for", section)

    def test_audit_names_the_trailing_dots_as_required(self):
        # --locate prefix-matches only when the query ends in "..." (a
        # round-3 restriction). forget says to paste the name as printed;
        # journey's newer copy did not, so a model could strip the suffix
        # and get a miss on a name that exists.
        section = flat(self.body[self.body.index("## Audit the description set"):])
        self.assertIn("trailing `...` included", section)

    def test_audit_resolves_files_with_locate_not_paths(self):
        # --paths reports the first root only, so globbing it audits a
        # subset of the set the listing showed.
        section = flat(self.body[self.body.index("## Audit the description set"):])
        self.assertIn("bin/gl-journey --locate", section)
        self.assertIn("Do not glob the `skills-root:` from `--paths`", section)

    def test_description_audit_reads_the_files_not_the_clipped_listing(self):
        # The listing clips descriptions at DESC_CHARS, which cuts the
        # "use when" clause the audit's whole question turns on.
        self.assertIn("from the files", flat(self.body))
        self.assertIn("Open each `SKILL.md` and read its frontmatter",
                      flat(self.body))

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

    def test_shows_the_content_before_asking(self):
        # Confirmation without showing is a signature on a blank page, and
        # forget's own description promises "after showing exactly what will
        # be removed". Deleting the whole Show section left the suite green.
        self.assertIn("## Show", self.body)
        self.assertIn("print exactly what will be removed, not a summary",
                      flat(self.body))

    def test_forbids_tombstones(self):
        self.assertIn("Delete, do not soften", self.body)
        self.assertIn("deprecated", self.body)

    def test_deletes_the_whole_directory_not_just_the_file(self):
        # "<slug>/" is a substring of "<slug>/SKILL.md", so the old
        # assertion passed on the exact regression it named. The directory
        # matters: --locate prints a directory precisely because that is
        # what gets removed, supporting files included.
        self.assertIn("delete the whole `<slug>/` directory", flat(self.body))
        self.assertIn("not just `SKILL.md`", flat(self.body))

    def test_reports_referrers_rather_than_cascading_the_deletion(self):
        # The section used to instruct removing "derived entries" - other
        # skills and profile lines that referenced the deleted one. That
        # deleted items which were never located, never shown and never
        # confirmed, on the authority of a yes given for something else,
        # from inside the one skill built to be that gate.
        self.assertIn("Report what you find. Do not delete it.", flat(self.body))
        self.assertIn("List the referrers and stop", flat(self.body))

    def test_uses_locate_and_handles_every_outcome(self):
        # Without a branch per outcome, a miss reads as "does not exist" and
        # the by-topic path falls back to the reconstructed path --locate
        # exists to replace.
        self.assertIn("--locate", self.body)
        for outcome in ("One line", "More than one line", "no skill named"):
            self.assertIn(outcome, self.body)
        self.assertIn("does not apply", self.body)   # the profile-line case
        # The listing clips names; without this the model has no way to
        # know the clipped form it just read is a valid query.
        self.assertIn("matches the clipped form too", flat(self.body))

    def test_asks_first_on_ambiguous_scope(self):
        self.assertIn("ambiguous", self.body.lower())

    def test_locates_via_explicit_journey_path(self):
        # Explicit path required - bare `gl-journey` is not on PATH inside a
        # plugin skill (measured empirically).
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey', self.body)


class TestScriptInvocationAllowedTools(unittest.TestCase):
    """The six skills that shell out to a bin/ script must pin an
    allowed-tools rule on the same ${CLAUDE_PLUGIN_ROOT} path they invoke in
    the body, or every invocation stops for a permission prompt."""

    CASES = {
        "learn": "gl-journey",
        "jot": "gl-journey",
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
