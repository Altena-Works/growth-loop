import json
import os
import re
import unittest

from fixtures import BIN, PLUGIN_ROOT

SCRIPTS = ("gl-recall", "gl-nudge", "gl-journey")
FORBIDDEN_IMPORTS = re.compile(
    r"^\s*(?:import|from)\s+(requests|urllib|http|socket|ssl|ftplib|smtplib|"
    r"telnetlib|xmlrpc|numpy|yaml|pydantic|httpx|aiohttp)\b", re.MULTILINE)
# OUT rows: never reimplement a built-in.
FORBIDDEN_FEATURES = ("crontab", "schedule.every", "subprocess.Popen",
                      "telegram", "discord", "mcp_server", "text-to-speech")
# The compliance constraint the spec states first and the suite never checked:
# no OAuth token is read, extracted, proxied, or passed anywhere. Routing
# subscription credentials through third-party tools is prohibited, so the
# absence has to be enforced mechanically rather than assumed.
CREDENTIAL_TOKENS = ("oauth", "access_token", "refresh_token", "api_key",
                     "apikey", "bearer", "credential", "keychain",
                     "ANTHROPIC_API_KEY", ".credentials.json")


class TestHooks(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text())

    def test_registers_both_events(self):
        self.assertEqual(sorted(self.data["hooks"].keys()), ["SessionEnd", "Stop"])

    def test_both_point_at_gl_nudge_via_plugin_root(self):
        for event in ("Stop", "SessionEnd"):
            entry = self.data["hooks"][event][0]["hooks"][0]
            self.assertEqual(entry["type"], "command")
            self.assertIn("${CLAUDE_PLUGIN_ROOT}", entry["command"])
            self.assertTrue(entry["command"].endswith("/bin/gl-nudge"))

    def test_no_blocking_configuration(self):
        raw = (PLUGIN_ROOT / "hooks" / "hooks.json").read_text()
        self.assertNotIn("block", raw)


class TestScriptConstraints(unittest.TestCase):
    def test_shebang_and_executable_bit(self):
        for name in SCRIPTS:
            path = BIN / name
            self.assertTrue(path.exists(), name)
            self.assertEqual(path.read_text().splitlines()[0],
                             "#!/usr/bin/env python3", name)
            self.assertTrue(os.access(path, os.X_OK),
                            "%s is not executable; the hook depends on it" % name)

    def test_stdlib_only_and_offline(self):
        for name in SCRIPTS:
            source = (BIN / name).read_text()
            hit = FORBIDDEN_IMPORTS.search(source)
            self.assertIsNone(hit, "%s imports %s" % (name, hit.group(1) if hit else ""))

    def test_no_out_row_features(self):
        for name in SCRIPTS:
            source = (BIN / name).read_text().lower()
            for feature in FORBIDDEN_FEATURES:
                self.assertNotIn(feature.lower(), source,
                                 "%s reimplements an OUT-row built-in" % name)

    def test_nothing_touches_credentials(self):
        # Covers the whole plugin, not just bin/: a skill body instructing the
        # model to read a token would breach the constraint just as squarely
        # as a script doing it.
        targets = [BIN / name for name in SCRIPTS]
        targets += sorted((PLUGIN_ROOT / "skills").glob("*/SKILL.md"))
        targets += sorted((PLUGIN_ROOT / "agents").glob("*.md"))
        targets.append(PLUGIN_ROOT / "hooks" / "hooks.json")
        for target in targets:
            source = target.read_text().lower()
            for token in CREDENTIAL_TOKENS:
                self.assertNotIn(token.lower(), source,
                                 "%s references %r" % (target.name, token))


class TestEnvironmentDefaults(unittest.TestCase):
    """A set-but-empty env var must fall back, not resolve to the cwd.

    The behaviour is exercised end to end for gl-journey via --paths. Doing
    the same for gl-nudge would make it write to the operator's real
    ~/.claude/growth-loop, so its guarantee is pinned at the source instead.
    """

    def test_home_falls_back_on_an_empty_value(self):
        for name in ("gl-journey", "gl-nudge"):
            source = (BIN / name).read_text()
            self.assertIn('os.environ.get("GROWTH_LOOP_HOME") or DEFAULT_HOME',
                          source,
                          "%s treats a set-but-empty GROWTH_LOOP_HOME as an "
                          "override, resolving state into the cwd" % name)

    def test_state_is_stamped_before_the_ledger_is_appended(self):
        """The ordering carries the anti-habituation guarantee.

        If the ledger append succeeds and the state write then fails, the
        message still prints but last_nudge was never persisted, so the next
        heavy session fires again well inside the cooldown. A partial-write
        failure cannot be provoked from a test, so the ordering is pinned at
        the source — the code comment already says not to reorder it.
        """
        source = (BIN / "gl-nudge").read_text()
        body = source[source.index("def record("):source.index("def message(")]
        self.assertLess(body.index("nudge-state.json"), body.index("ledger.jsonl"),
                        "record() appends to the ledger before stamping the "
                        "cooldown; a failed state write then leaves the nudge "
                        "firing inside its own cooldown window")


class TestTuningTableMatchesTheSource(unittest.TestCase):
    """The README's Tuning table is the only place these numbers are

    explained, and the section tells the reader to go edit them. Nothing
    checked that the documented value is the shipped one, so every default
    could drift silently — the cooldown especially, which the README calls
    the anti-habituation guarantee while only the existence of a cooldown
    was pinned, never its value.
    """

    DOCUMENTED = {
        "gl-nudge": [("MIN_TOOL_CALLS", "25"), ("MIN_EDITS", "3"),
                     ("COOLDOWN_SECONDS", "21600")],
        "gl-journey": [("STALE_DAYS", "90")],
        "gl-recall": [("DEFAULT_MAX", "25"), ("DEFAULT_DAYS", "90"),
                      ("SNIPPET_CHARS", "400")],
    }

    def setUp(self):
        self.readme = (PLUGIN_ROOT / "README.md").read_text()

    def test_every_documented_default_is_the_shipped_one(self):
        for script, entries in self.DOCUMENTED.items():
            source = (BIN / script).read_text()
            for name, value in entries:
                line = [l for l in source.splitlines()
                        if l.startswith("%s = " % name)]
                self.assertEqual(len(line), 1, "%s: %s not found" % (script, name))
                actual = line[0].split("=", 1)[1].split("#")[0].strip()
                # COOLDOWN_SECONDS ships as an expression (6 * 3600).
                self.assertEqual(str(eval(actual, {}, {})), value,
                                 "%s ships %s = %s but the README's Tuning "
                                 "table documents %s"
                                 % (script, name, actual, value))

    def test_every_documented_default_appears_in_the_table(self):
        table = [l for l in self.readme.splitlines()
                 if l.startswith("| `") and l.count("|") >= 4]
        documented = {row.split("|")[1].strip().strip("`") for row in table}
        for script, entries in self.DOCUMENTED.items():
            for name, _ in entries:
                self.assertIn(name, documented,
                              "%s is tunable but absent from the README table"
                              % name)

    def test_journeys_review_threshold_is_documented_where_it_lives(self):
        # The verdict age is not a script constant - it is the --stale value
        # journey passes. The table has to name that separately or a tuner
        # edits STALE_DAYS and nothing about the review changes.
        self.assertIn("skills/journey/SKILL.md", self.readme)
        body = (PLUGIN_ROOT / "skills" / "journey" / "SKILL.md").read_text()
        self.assertIn("--stale 60", body)


if __name__ == "__main__":
    unittest.main()
