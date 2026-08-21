import json
import unittest

from fixtures import EXPECTED_TREE, PLUGIN_ROOT


class TestManifest(unittest.TestCase):
    def test_manifest_parses_and_has_required_fields(self):
        data = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(data["name"], "growth-loop")
        # Not a hardcoded literal: that needs editing on every release and
        # still cannot see the marketplace entry drifting away from it.
        self.assertRegex(data["version"], r"^\d+\.\d+\.\d+$")
        self.assertIn("description", data)
        self.assertIn("author", data)

    def test_the_marketplace_entry_declares_the_same_version(self):
        # Two manifests carry the version. A release that bumps one and not
        # the other installs a plugin whose catalogue entry disagrees with
        # what it actually is.
        plugin = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())
        market = json.loads(
            (PLUGIN_ROOT.parent / ".claude-plugin" / "marketplace.json").read_text())
        entries = [p for p in market["plugins"] if p["name"] == plugin["name"]]
        self.assertEqual(len(entries), 1, market["plugins"])
        self.assertEqual(entries[0]["version"], plugin["version"])

    def test_description_names_all_five_loop_stages(self):
        data = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())
        desc = data["description"].lower()
        for stage in ("distil", "refine", "nudge", "recall", "model"):
            self.assertIn(stage, desc, "description must name the %s stage" % stage)

    def test_manifest_declares_no_custom_hooks_path(self):
        # hooks/hooks.json is a default location; declaring it again is a
        # conflicting-manifest error in Claude Code.
        data = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())
        self.assertNotIn("hooks", data)

    def test_claude_plugin_dir_contains_only_the_manifest(self):
        entries = sorted(p.name for p in (PLUGIN_ROOT / ".claude-plugin").iterdir())
        self.assertEqual(entries, ["plugin.json"])

    def test_no_unexpected_files_in_the_plugin(self):
        # Completeness (all 13 present) is asserted once, in Task 9's
        # tests/test_completeness.py. Here we only guard against strays, so
        # this module stays green from Task 1 onward.
        found = {
            str(p.relative_to(PLUGIN_ROOT))
            for p in PLUGIN_ROOT.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
        }
        self.assertEqual(found - set(EXPECTED_TREE), set())


if __name__ == "__main__":
    unittest.main()
