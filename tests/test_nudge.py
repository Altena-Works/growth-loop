import json
import shutil
import unittest

from fixtures import hook_payload, run, tmpdir, write_transcript


class TestNudge(unittest.TestCase):
    def setUp(self):
        self.home = tmpdir()
        self.work = tmpdir()
        self.env = {"GROWTH_LOOP_HOME": str(self.home)}
        self.heavy = write_transcript(
            self.work / "heavy.jsonl", "do the migration", "done",
            tool_calls=30, file_paths=["/r/a.py", "/r/b.py", "/r/c.py", "/r/d.py"])
        self.light = write_transcript(
            self.work / "light.jsonl", "what is 2+2", "4", tool_calls=2,
            file_paths=["/r/a.py"])

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)
        shutil.rmtree(self.work, ignore_errors=True)

    def test_heavy_session_fires_with_stop_payload_shape(self):
        code, out, _ = run("gl-nudge", [], env=self.env,
                           stdin=hook_payload(self.heavy, "Stop"))
        self.assertEqual(code, 0)
        payload = json.loads(out)
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "Stop")
        self.assertNotIn("decision", payload)      # must never block the stop
        self.assertIn("30", context)
        self.assertIn("/growth-loop:learn", context)
        self.assertIn("/growth-loop:profile", context)
        self.assertIn("say nothing and move on", context)

    def test_session_end_uses_system_message_not_additional_context(self):
        code, out, _ = run("gl-nudge", [], env=self.env,
                           stdin=hook_payload(self.heavy, "SessionEnd"))
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertIn("systemMessage", payload)
        self.assertNotIn("hookSpecificOutput", payload)

    def test_ledger_and_state_are_written_on_fire(self):
        run("gl-nudge", [], env=self.env, stdin=hook_payload(self.heavy, "Stop"))
        entries = [json.loads(l) for l in
                   (self.home / "ledger.jsonl").read_text().splitlines() if l.strip()]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["stats"]["tool_calls"], 30)
        self.assertEqual(entries[0]["stats"]["edits"], 30)
        self.assertEqual(len(entries[0]["stats"]["files"]), 4)
        self.assertEqual(entries[0]["session"], "sess-abc123")
        state = json.loads((self.home / "nudge-state.json").read_text())
        self.assertIn("last_nudge", state)

    def test_second_identical_invocation_is_silent_cooldown(self):
        run("gl-nudge", [], env=self.env, stdin=hook_payload(self.heavy, "Stop"))
        code, out, _ = run("gl-nudge", [], env=self.env,
                           stdin=hook_payload(self.heavy, "Stop"))
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "")
        entries = [l for l in (self.home / "ledger.jsonl").read_text().splitlines()
                   if l.strip()]
        self.assertEqual(len(entries), 1)

    def test_light_session_stays_silent(self):
        code, out, _ = run("gl-nudge", [], env=self.env,
                           stdin=hook_payload(self.light, "Stop"))
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "")
        self.assertFalse((self.home / "ledger.jsonl").exists())

    def test_many_calls_but_few_edits_stays_silent(self):
        readonly = write_transcript(self.work / "reads.jsonl", "explore", "ok",
                                    tool_calls=40, tool_name="Read",
                                    file_paths=["/r/a.py"])
        code, out, _ = run("gl-nudge", [], env=self.env,
                           stdin=hook_payload(readonly, "Stop"))
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "")

    def test_todowrite_does_not_count_as_an_edit(self):
        readonly = write_transcript(self.work / "investigation.jsonl",
                                    "explore the failure", "found it",
                                    tool_calls=22, tool_name="Read",
                                    file_paths=["/r/a.py"])
        todos = write_transcript(self.work / "todos.jsonl", "plan it", "planned",
                                 tool_calls=3, tool_name="TodoWrite", file_paths=())
        # Splice the TodoWrite calls onto the end of the read-only transcript:
        # 22 reads + 3 TodoWrite calls crosses MIN_TOOL_CALLS (25) but must
        # still count zero edits, since neither tool touches a file.
        combined = self.work / "combined.jsonl"
        combined.write_text(
            readonly.read_text(encoding="utf-8").rstrip("\n") + "\n" +
            todos.read_text(encoding="utf-8"), encoding="utf-8")
        code, out, _ = run("gl-nudge", [], env=self.env,
                           stdin=hook_payload(combined, "Stop"))
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "")
        self.assertFalse((self.home / "ledger.jsonl").exists())

    def test_missing_stdin_exits_zero_silently(self):
        code, out, err = run("gl-nudge", [], env=self.env, stdin="")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "")
        self.assertEqual(err.strip(), "")

    def test_garbage_stdin_exits_zero_silently(self):
        code, out, err = run("gl-nudge", [], env=self.env, stdin="not json at all")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "")
        self.assertEqual(err.strip(), "")

    def test_missing_transcript_exits_zero_silently(self):
        code, out, err = run("gl-nudge", [], env=self.env,
                             stdin=hook_payload(self.work / "gone.jsonl", "Stop"))
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "")
        self.assertEqual(err.strip(), "")

    def test_unwritable_home_still_exits_zero(self):
        code, out, err = run("gl-nudge", [],
                             env={"GROWTH_LOOP_HOME": "/dev/null/nope"},
                             stdin=hook_payload(self.heavy, "Stop"))
        self.assertEqual(code, 0)
        self.assertEqual(err.strip(), "")


if __name__ == "__main__":
    unittest.main()
