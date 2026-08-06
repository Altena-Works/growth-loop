import shutil
import unittest

from fixtures import load_script, run, tmpdir, write_transcript


class TestRecall(unittest.TestCase):
    def setUp(self):
        self.root = tmpdir()
        self.env = {"CLAUDE_TRANSCRIPT_DIR": str(self.root)}
        write_transcript(
            self.root / "projects" / "myrepo" / "sess-0001.jsonl",
            user_text="the deploy kept failing with ECONNREFUSED on port 5432",
            assistant_text="We fixed it by pointing DATABASE_URL at the socket path.",
            tool_calls=3, file_paths=["/repo/app.py"],
        )

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_list_roots_reports_the_env_root(self):
        code, out, _ = run("gl-recall", ["--list-roots"], env=self.env)
        self.assertEqual(code, 0)
        self.assertIn(str(self.root), out)

    def test_query_matches_and_prints_the_turn(self):
        code, out, _ = run("gl-recall", ["ECONNREFUSED"], env=self.env)
        self.assertEqual(code, 0)
        self.assertIn("ECONNREFUSED", out)
        self.assertIn("sess-0001", out)
        self.assertIn("1 match(es) across 1 session(s)", out)

    def test_regex_query_works(self):
        code, out, _ = run("gl-recall", [r"port \d+"], env=self.env)
        self.assertEqual(code, 0)
        self.assertIn("5432", out)

    def test_invalid_regex_falls_back_to_literal(self):
        write_transcript(self.root / "projects" / "myrepo" / "sess-0002.jsonl",
                         user_text="what does foo( do", assistant_text="nothing")
        code, out, _ = run("gl-recall", ["foo("], env=self.env)
        self.assertEqual(code, 0)
        self.assertIn("foo(", out)

    def test_tool_use_blocks_are_searchable(self):
        code, out, _ = run("gl-recall", ["/repo/app.py"], env=self.env)
        self.assertEqual(code, 0)
        self.assertIn("[Edit]", out)

    def test_no_match_exits_zero(self):
        code, out, _ = run("gl-recall", ["zzzznotpresent"], env=self.env)
        self.assertEqual(code, 0)
        self.assertIn("0 match(es)", out)

    def test_corrupt_lines_do_not_crash(self):
        # write_transcript appends an invalid JSON line to every fixture.
        code, _, err = run("gl-recall", ["deploy"], env=self.env)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")

    def test_empty_roots_exit_one_with_remedy(self):
        empty = tmpdir() / "nowhere"
        code, out, err = run("gl-recall", ["anything"],
                             env={"CLAUDE_TRANSCRIPT_DIR": str(empty)})
        self.assertEqual(code, 1)
        combined = out + err
        self.assertIn("CLAUDE_TRANSCRIPT_DIR", combined)
        self.assertIn(str(empty), combined)

    def test_max_flag_caps_output(self):
        for i in range(10):
            write_transcript(self.root / "projects" / "myrepo" / ("s-%02d.jsonl" % i),
                             user_text="needle here", assistant_text="ok")
        code, out, _ = run("gl-recall", ["needle", "--max", "3"], env=self.env)
        self.assertEqual(code, 0)
        self.assertIn("3 match(es)", out)

    def test_truncated_tool_input_carries_a_marker(self):
        # Asserting "..." appears in the rendered output is worthless here:
        # window() independently adds one whenever the snippet is not flush
        # with the record boundary, which it never is - a version with the
        # marker stripped from clip() still passed. Load the function and
        # check it directly.
        clip = load_script("gl-recall").clip
        self.assertEqual(clip("abcdef", 10), "abcdef")
        self.assertEqual(clip("abcdef", 6), "abcdef")
        self.assertEqual(clip("abcdef", 4), "abcd...")
        self.assertTrue(clip("d" * 500, 200).endswith("..."))
        self.assertEqual(len(clip("d" * 500, 200)), 203)

    def test_list_roots_survives_an_unreadable_subtree(self):
        blocked = self.root / "projects" / "locked"
        blocked.mkdir(parents=True)
        (blocked / "x.jsonl").write_text("{}\n", encoding="utf-8")
        blocked.chmod(0o000)
        try:
            code, out, err = run("gl-recall", ["--list-roots"], env=self.env)
            self.assertEqual(code, 0)
            self.assertEqual(err.strip(), "")
            self.assertIn(str(self.root), out)
        finally:
            blocked.chmod(0o755)


if __name__ == "__main__":
    unittest.main()
