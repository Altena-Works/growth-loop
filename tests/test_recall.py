import os
import pathlib
import shutil
import time
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

    def test_cap_is_announced_with_an_accurate_unread_count(self):
        # The headline change of a whole round shipped with no test. The
        # count must be sessions *read*, not sessions that matched: using
        # the latter reported nearly every transcript as unread on any
        # selective query, and that number is the sole basis for deciding
        # how far to raise --max.
        # Back-date explicitly: the search reads newest first, so the count
        # only means anything against a known order.
        aged = self.root / "projects" / "aged"
        plan = [("quiet-0", "nothing here", 1), ("quiet-1", "nothing here", 2),
                ("hit-0", "NEEDLEWORD a", 3), ("hit-1", "NEEDLEWORD b", 4),
                ("hit-2", "NEEDLEWORD c", 5), ("hit-3", "NEEDLEWORD d", 6)]
        for name, text, age in plan:
            path = write_transcript(aged / (name + ".jsonl"),
                                    user_text=text, assistant_text="ok")
            stamp = time.time() - age * 86400
            os.utime(path, (stamp, stamp))
        # Two quiet sessions read, then two hits fill --max 2 at index 4 of
        # 6 aged files. Anything the setUp fixture adds is newer than all of
        # them, so it is read first and counted in index too.
        code, out, _ = run("gl-recall", ["NEEDLEWORD", "--max", "2"], env=self.env)
        self.assertEqual(code, 0)
        self.assertIn("stopped at the --max limit of 2", out)
        tail = out[out.index("stopped at the"):]
        self.assertIn("2 older session(s) were not read", tail,
                      "the count must be sessions read, not sessions matched")

    def test_cap_filled_on_the_last_session_still_announces(self):
        # Silence there is byte-identical to an exhausted search, which is
        # the one thing this plugin says a truncation must never look like.
        path = write_transcript(self.root / "projects" / "r" / "dense.jsonl",
                                user_text="NEEDLEWORD one",
                                assistant_text="NEEDLEWORD two")
        # Oldest, so nothing remains unread once the cap fills on it — the
        # branch that used to print nothing at all.
        stamp = time.time() - 300 * 86400
        os.utime(path, (stamp, stamp))
        code, out, _ = run("gl-recall", ["NEEDLEWORD", "--days", "365",
                                         "--max", "1"], env=self.env)
        self.assertEqual(code, 0)
        self.assertIn("stopped at the --max limit", out)

    def test_an_exhausted_search_says_nothing_about_the_cap(self):
        code, out, _ = run("gl-recall", ["ECONNREFUSED", "--max", "50"], env=self.env)
        self.assertEqual(code, 0)
        self.assertNotIn("stopped at the --max limit", out)

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

    def test_jsonl_files_survives_an_error_while_iterating(self):
        # The previous version of this test chmod-ed a subtree to 000 and
        # asserted the CLI still exited 0. It could not fail: pathlib's
        # rglob swallows PermissionError internally, so no version of the
        # code — including one with the guard deleted entirely — ever
        # reached an exception path. Drive the failure directly instead.
        jsonl_files = load_script("gl-recall").jsonl_files

        class Exploding:
            def rglob(self, pattern):
                yield pathlib.Path("/one.jsonl")
                raise OSError("filesystem went away mid-walk")

        self.assertEqual(list(jsonl_files(Exploding())),
                         [pathlib.Path("/one.jsonl")],
                         "an error while iterating must stop the walk, not "
                         "propagate and not lose what was already found")

if __name__ == "__main__":
    unittest.main()
