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


if __name__ == "__main__":
    unittest.main()
