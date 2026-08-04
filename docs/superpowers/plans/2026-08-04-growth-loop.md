# growth-loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `growth-loop`, an installable Claude Code plugin that closes the learning loop — work finishes → knowledge is captured as skills and profile entries → capture is reviewed → stale capture is deleted.

**Architecture:** Three Python-stdlib CLIs in `bin/` do all deterministic work (transcript search, session-weight measurement, asset inventory) so the model never burns context grepping. Six `SKILL.md` files carry the judgment (when to distil, when to correct, when to delete). One `Stop`/`SessionEnd` hook feeds an advisory nudge into the session via `hookSpecificOutput.additionalContext`. Nothing runs outside the official harness; no token is read or proxied.

**Tech Stack:** Python 3 stdlib only (no pip, no network), Markdown + YAML frontmatter, JSON manifests. Target harness: Claude Code v2.1.221 (verified locally).

## Repository layout

The project root is `/Users/kn/File/projects/claude/growth-loop/`. The **plugin** is the nested `growth-loop/` directory, so the spec's own verification command works verbatim from the project root:

```
claude/growth-loop/                 ← project root (git repo)
├── growth-loop/                    ← THE PLUGIN — must match spec §4 exactly, 13 files
├── tests/                          ← test suite (not shipped, not part of the 13)
└── docs/superpowers/plans/         ← this plan
```

`claude --plugin-dir ./growth-loop` and `claude plugin validate ./growth-loop` are both run from the project root.

## Global Constraints

Every task's requirements implicitly include this section.

- **Python 3 stdlib only.** No pip installs, no non-stdlib imports, no network calls (`urllib`, `socket`, `http`, `requests` are all forbidden in `bin/`), no telemetry. Scripts read local files and print text.
- **Exit 0 in every failure path** for `bin/gl-nudge`. Missing payload, unreadable transcript, corrupt JSON lines, unwritable state dir — all silent, all exit 0. A hook must never break a session.
- **Corrupt-JSONL tolerance** in all three scripts: skip the bad line, never crash.
- **No OAuth token is read, extracted, proxied, or passed anywhere.** Everything runs inside the official harness.
- **No component may encourage or enable unattended 24/7 operation.** The plugin is for interactive sessions.
- **Never implement an OUT-row feature** (cron/scheduling, subagent orchestration, chat surfaces, terminal backends, MCP, compress/undo/retry, image/video/TTS). If a built-in turns out to cover part of an IN row, shrink scope and report it — do not duplicate.
- **Privacy:** the profile skill must explicitly exclude health, finances, relationships, politics, and anything inferred rather than stated. Omit entirely; never write vague placeholders.
- **Persistent state:** `~/.claude/growth-loop/` holding `profile.md`, `ledger.jsonl`, `nudge-state.json`; overridable by `GROWTH_LOOP_HOME`. Distilled skills are written to `~/.claude/skills/<slug>/SKILL.md`.
- **Shebang** `#!/usr/bin/env python3` on all three `bin/` scripts; all three `chmod +x`.
- **Plugin tree:** nothing but `plugin.json` inside `.claude-plugin/`. `skills/`, `agents/`, `hooks/`, `bin/` sit at the plugin root.
- **Tunable constants at the top of the file**, each with a comment saying it is tunable and why the conservative default matters.
- **Commit hygiene:** `.claude-plugin/` here is a *project deliverable* (the plugin's own manifest), not agent operating context — the global "never commit `.claude/`" rule does not apply to it. Do commit it.

## Verified against live docs — 2026-08-04

The planner re-ran spec §3 against `code.claude.com/docs` and this machine. **If the build starts more than ~1 week after this date, re-verify §3 before Task 1.** Findings that change the design:

| Spec §3 claim | Verified result | Consequence |
|---|---|---|
| Only `plugin.json` in `.claude-plugin/`; `bin/` on the Bash PATH | **Confirmed.** "Executables added to the Bash tool's `PATH`. Files here are invokable as bare commands in any Bash tool call while the plugin is enabled." | As specced. |
| `hooks/hooks.json` at plugin root | **Confirmed** as a default location (`"Location: hooks/hooks.json in plugin root, or inline in plugin.json"`). Manifest key `"hooks": "./config/hooks.json"` is only for custom paths. | Do **not** add a `hooks` key to `plugin.json`. |
| Plugin skills namespaced `/growth-loop:learn` | **Confirmed.** For plugin skills the frontmatter `name` sets the last command segment. | Every SKILL.md needs a correct `name`. |
| `disable-model-invocation` still exists | **Confirmed**, exact name unchanged. | `journey`/`forget` use it. |
| Description cap ~1024 chars | **DIVERGENCE.** `description` + `when_to_use` are truncated at **1,536** characters combined in the skill listing. | Cap enforced at 1,536 in the linter; still aim for well under. |
| Stop exit 2 blocks the stop | **Confirmed**, and it burns the consecutive-block cap. | Forbidden for the nudge. |
| Stop exit-0 output visibility (§9 uncertainty 2) | **RESOLVED.** Stop, exit 0 with JSON → `hookSpecificOutput.additionalContext` is delivered to Claude via a system reminder on the next model call. | **This is the nudge's delivery mechanism.** No transcript-only fallback needed. |
| SessionEnd delivery | **DIVERGENCE from the spec's assumption of symmetry.** SessionEnd exit-0 JSON stdout is "added as context (**not shown to Claude**)"; SessionEnd cannot block and exit 2 is ignored. There is no next model call anyway. | SessionEnd fires a **user-facing** `systemMessage` + ledger write, not `additionalContext`. Both registrations share one cooldown so a Stop nudge is not immediately followed by a SessionEnd nudge. Document this asymmetry in the README. |
| `$ARGUMENTS` | **Confirmed**, plus `$ARGUMENTS[N]` / `$N`. If `$ARGUMENTS` is absent from the body, args are appended as `ARGUMENTS: <value>`. | `learn` and `forget` use `$ARGUMENTS` explicitly. |
| Transcript roots (§9 uncertainty 1) | **Resolved empirically on this machine:** `~/.claude/projects` exists with 3,308 `.jsonl`; `~/.claude/sessions` exists but empty; `~/.config/claude/projects` and both macOS Application Support paths are absent. | Keep full autodiscovery regardless; order `~/.claude/projects` first. |
| — | **New:** `claude plugin validate ./my-plugin` exists and checks `plugin.json`, skill/agent/command frontmatter, and `hooks/hooks.json`. | Added to the verification protocol. |
| — | **New:** `plugin.json` is now *optional* (components auto-discovered, name from directory). | Ship it anyway — spec §5.1 requires it and it carries the description. |
| Local environment | Python 3.11.9, Claude Code 2.1.221, `~/.claude/skills/` already holds 9 personal skills. | `gl-journey` will find real entries on first run; that is expected, not a bug. |

**Neighbouring projects — checked for OUT-row overlap.** `claude/claude-personality-learn` (daily Gemini-driven profile accumulation from CLAUDE.md files) and `claude/claude-transcript-organizer` (batch transcript → per-project HANDOFF.md) are both **external batch CLIs that call an LLM API**. growth-loop is in-session and never calls an API. Conceptual adjacency, zero implementation overlap — no scope shrink required. Do not import from or depend on either.

## File Structure

**Plugin (the 13 files of spec §4):**

| File | Responsibility |
|---|---|
| `growth-loop/.claude-plugin/plugin.json` | Manifest: name, version, description naming the five loop stages, author. |
| `growth-loop/README.md` | What it adds, non-goals table, install, verification, tuning, design notes, usage-limits note. |
| `growth-loop/skills/learn/SKILL.md` | Distil a skill from finished work. Model-invoked. |
| `growth-loop/skills/refine/SKILL.md` | Correct a skill the moment it proves wrong. Model-invoked. |
| `growth-loop/skills/recall/SKILL.md` | Recover context from past sessions. Model-invoked. |
| `growth-loop/skills/profile/SKILL.md` | Maintain the cross-project user model. Model-invoked. |
| `growth-loop/skills/journey/SKILL.md` | Monthly review with forced verdicts. User-invoked only. |
| `growth-loop/skills/forget/SKILL.md` | Deletion as a first-class operation. User-invoked only. |
| `growth-loop/agents/skill-author.md` | Subagent that writes skill documents and nothing else. |
| `growth-loop/hooks/hooks.json` | Registers `gl-nudge` on `Stop` and `SessionEnd`. |
| `growth-loop/bin/gl-recall` | Deterministic transcript search. |
| `growth-loop/bin/gl-nudge` | Session-weight heuristic + cooldown + ledger. |
| `growth-loop/bin/gl-journey` | Asset inventory with staleness. |

**Test suite (not shipped):**

| File | Responsibility |
|---|---|
| `tests/fixtures.py` | Builds the synthetic transcript / skill / state fixtures in a `tempfile` dir. Shared by every test module. |
| `tests/test_manifest.py` | `plugin.json` parses; required fields; `.claude-plugin/` contains only `plugin.json`; no stray files anywhere in the plugin. |
| `tests/test_completeness.py` | Created in Task 9: the plugin tree is exactly the 13 files of spec §4. |
| `tests/test_recall.py` | `gl-recall` root discovery, env override, regex + literal fallback, grouping, empty-state exit 1. |
| `tests/test_nudge.py` | `gl-nudge` thresholds, cooldown, ledger append, Stop vs SessionEnd payload shape, every failure path exits 0 silently. |
| `tests/test_journey.py` | `gl-journey` skill discovery, dedupe, description extraction, staleness, `--stale N`, memory + ledger sections. |
| `tests/test_skills.py` | Frontmatter linter over all six SKILL.md + the agent: name/description present, ≤1,536 chars, invocation flags correct, required headings present, body < 500 lines. |
| `tests/test_constraints.py` | No non-stdlib imports, no network imports, no OUT-row feature strings, shebangs correct, `bin/*` executable. |
| `tests/run.py` | `python3 -m unittest discover`-equivalent entry point so one command runs everything. |

---

### Task 1: Project scaffold, manifest, and the tree test

**Files:**
- Create: `.gitignore`, `growth-loop/.claude-plugin/plugin.json`
- Create: `tests/fixtures.py`, `tests/test_manifest.py`, `tests/run.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `tests.fixtures.PLUGIN_ROOT` (`pathlib.Path` to `growth-loop/`), `tests.fixtures.PROJECT_ROOT`, `tests.fixtures.EXPECTED_TREE` (`frozenset[str]` of the 13 relative paths). Later tasks import these.

- [ ] **Step 1: Initialise the repo**

```bash
cd /Users/kn/File/projects/claude/growth-loop
git init
printf '__pycache__/\n*.pyc\n.DS_Store\n' > .gitignore
mkdir -p growth-loop/.claude-plugin growth-loop/skills growth-loop/agents growth-loop/hooks growth-loop/bin tests
```

- [ ] **Step 2: Write the shared fixtures module**

Create `tests/fixtures.py`:

```python
"""Shared paths and fixture builders for the growth-loop test suite."""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = PROJECT_ROOT / "growth-loop"
BIN = PLUGIN_ROOT / "bin"

EXPECTED_TREE = frozenset({
    ".claude-plugin/plugin.json",
    "README.md",
    "skills/learn/SKILL.md",
    "skills/refine/SKILL.md",
    "skills/recall/SKILL.md",
    "skills/profile/SKILL.md",
    "skills/journey/SKILL.md",
    "skills/forget/SKILL.md",
    "agents/skill-author.md",
    "hooks/hooks.json",
    "bin/gl-recall",
    "bin/gl-nudge",
    "bin/gl-journey",
})

MODEL_INVOKED = ("learn", "refine", "recall", "profile")
USER_INVOKED_ONLY = ("journey", "forget")


def run(script, args, env=None, stdin=None):
    """Run a bin/ script. Returns (returncode, stdout, stderr)."""
    environ = dict(os.environ)
    environ.pop("CLAUDE_TRANSCRIPT_DIR", None)
    environ.pop("GROWTH_LOOP_HOME", None)
    if env:
        environ.update(env)
    proc = subprocess.run(
        [sys.executable, str(BIN / script)] + list(args),
        input=stdin, capture_output=True, text=True, env=environ,
    )
    return proc.returncode, proc.stdout, proc.stderr


def tmpdir():
    """A temp dir that the caller is responsible for cleaning up."""
    return Path(tempfile.mkdtemp(prefix="growth-loop-test-"))


def write_transcript(path, user_text, assistant_text, tool_calls=0,
                     tool_name="Edit", file_paths=()):
    """Write a synthetic JSONL transcript.

    Emits one user turn, one assistant text turn, then `tool_calls` tool_use
    blocks cycling through `file_paths`, then one deliberately corrupt line.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        {"type": "user", "message": {"role": "user",
                                     "content": [{"type": "text", "text": user_text}]}},
        {"type": "assistant", "message": {"role": "assistant",
                                          "content": [{"type": "text", "text": assistant_text}]}},
    ]
    paths = list(file_paths) or ["/tmp/a.py"]
    for i in range(tool_calls):
        lines.append({"type": "assistant", "message": {"role": "assistant", "content": [{
            "type": "tool_use", "name": tool_name, "id": "t%d" % i,
            "input": {"file_path": paths[i % len(paths)], "old_string": "x", "new_string": "y"},
        }]}})
    with open(path, "w", encoding="utf-8") as fh:
        for rec in lines:
            fh.write(json.dumps(rec) + "\n")
        fh.write("{ this is not valid json\n")   # tolerance check
    return path


def write_skill(path, description, age_days=0):
    """Plant a SKILL.md with a given description and mtime age."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nname: %s\ndescription: %s\n---\n\nBody.\n" % (path.parent.name, description),
        encoding="utf-8",
    )
    if age_days:
        old = time.time() - age_days * 86400
        os.utime(path, (old, old))
    return path


def hook_payload(transcript_path, event="Stop", session_id="sess-abc123"):
    return json.dumps({
        "session_id": session_id,
        "transcript_path": str(transcript_path),
        "cwd": "/tmp",
        "hook_event_name": event,
    })
```

- [ ] **Step 3: Write the failing manifest test**

Create `tests/test_manifest.py`:

```python
import json
import unittest

from fixtures import EXPECTED_TREE, PLUGIN_ROOT


class TestManifest(unittest.TestCase):
    def test_manifest_parses_and_has_required_fields(self):
        data = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(data["name"], "growth-loop")
        self.assertEqual(data["version"], "0.1.0")
        self.assertIn("description", data)
        self.assertIn("author", data)

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
```

- [ ] **Step 4: Write the test runner**

Create `tests/run.py`:

```python
"""Run the whole growth-loop test suite: python3 tests/run.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `python3 tests/run.py`
Expected: FAIL — `FileNotFoundError` on `plugin.json`.

- [ ] **Step 6: Write the manifest**

Create `growth-loop/.claude-plugin/plugin.json`:

```json
{
  "name": "growth-loop",
  "displayName": "growth-loop",
  "version": "0.1.0",
  "description": "A closed learning loop for Claude Code: distil finished work into skills, refine them the moment they prove wrong, nudge you to persist what mattered, recall reasoning from past sessions, and model the person across projects.",
  "author": {
    "name": "4ltena",
    "url": "https://github.com/4ltena"
  },
  "license": "MIT",
  "keywords": ["skills", "memory", "learning-loop", "recall", "curation"]
}
```

- [ ] **Step 7: Run the test**

Run: `python3 tests/run.py`
Expected: **all five `TestManifest` cases PASS.** Every task in this plan ends with a fully green suite — a red test always means something is wrong.

- [ ] **Step 8: Commit**

```bash
git add .gitignore growth-loop/.claude-plugin/plugin.json tests/
git commit -m "feat: scaffold growth-loop plugin manifest and test harness"
```

---

### Task 2: `bin/gl-recall` — deterministic transcript search

**Files:**
- Create: `growth-loop/bin/gl-recall`
- Test: `tests/test_recall.py`

**Interfaces:**
- Consumes: `fixtures.run`, `fixtures.tmpdir`, `fixtures.write_transcript`.
- Produces: CLI contract `gl-recall [query] [--days N] [--max N] [--list-roots]`. Exit 0 on success (matches or none), exit 1 only when no transcript root exists. Stdout groups hits under `<session-id> (<mtime>)` headers and ends with `N match(es) across M session(s)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_recall.py`:

```python
import shutil
import unittest

from fixtures import run, tmpdir, write_transcript


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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 tests/run.py`
Expected: FAIL — `can't open file .../bin/gl-recall`.

- [ ] **Step 3: Implement `gl-recall`**

Create `growth-loop/bin/gl-recall`:

```python
#!/usr/bin/env python3
"""Search Claude Code session transcripts. Deterministic, stdlib-only, offline.

Searching transcripts with the model would burn the very context the loop
exists to protect, so the search happens out here and the model only reads
the summary.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

# Storage locations drift between versions and platforms; never hardcode one.
CANDIDATE_ROOTS = (
    "~/.claude/projects",
    "~/.claude/sessions",
    "~/.config/claude/projects",
    "~/Library/Application Support/Claude/projects",
    "~/Library/Application Support/ClaudeCode/projects",
)
SNIPPET_CHARS = 400          # tunable: window around each match
DEFAULT_DAYS = 90
DEFAULT_MAX = 25
TOOL_INPUT_CHARS = 200
TOOL_RESULT_CHARS = 200


def discover_roots():
    """Env override wins; otherwise every candidate that exists."""
    env = os.environ.get("CLAUDE_TRANSCRIPT_DIR")
    if env:
        candidates = [Path(p).expanduser() for p in env.split(os.pathsep) if p]
    else:
        candidates = [Path(c).expanduser() for c in CANDIDATE_ROOTS]
    roots, seen = [], set()
    for c in candidates:
        try:
            if not c.is_dir():
                continue
            key = str(c.resolve())
        except OSError:
            continue
        if key not in seen:
            seen.add(key)
            roots.append(c)
    return roots


def searched_paths():
    env = os.environ.get("CLAUDE_TRANSCRIPT_DIR")
    if env:
        return [str(Path(p).expanduser()) for p in env.split(os.pathsep) if p]
    return [str(Path(c).expanduser()) for c in CANDIDATE_ROOTS]


def transcripts(roots, days):
    cutoff = time.time() - days * 86400
    found = []
    for root in roots:
        try:
            files = root.rglob("*.jsonl")
        except OSError:
            continue
        for f in files:
            try:
                mtime = f.stat().st_mtime
            except OSError:
                continue
            if mtime >= cutoff:
                found.append((mtime, f))
    found.sort(key=lambda pair: pair[0], reverse=True)   # newest session first
    return found


def block_text(content):
    """Flatten a message content field into searchable text."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind == "text":
            parts.append(str(block.get("text", "")))
        elif kind == "tool_use":
            raw = json.dumps(block.get("input", {}), ensure_ascii=False)
            parts.append("[%s] %s" % (block.get("name", "tool"), raw[:TOOL_INPUT_CHARS]))
        elif kind == "tool_result":
            body = block.get("content")
            if not isinstance(body, str):
                body = json.dumps(body, ensure_ascii=False)
            parts.append("[result] " + body[:TOOL_RESULT_CHARS])
    return "\n".join(p for p in parts if p)


def records(path):
    """Yield (role, text) per line, skipping anything unparseable."""
    try:
        handle = open(path, "r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except (ValueError, TypeError):
                continue
            if not isinstance(rec, dict):
                continue
            message = rec.get("message")
            if not isinstance(message, dict):
                continue
            text = block_text(message.get("content"))
            if text:
                yield str(message.get("role", "?")), text


def window(text, match):
    half = SNIPPET_CHARS // 2
    start = max(0, match.start() - half)
    end = min(len(text), match.end() + half)
    snippet = text[start:end].replace("\n", " ")
    return ("..." if start > 0 else "") + snippet + ("..." if end < len(text) else "")


def build_pattern(query):
    try:
        return re.compile(query, re.IGNORECASE)
    except re.error:
        return re.compile(re.escape(query), re.IGNORECASE)


def main():
    parser = argparse.ArgumentParser(
        description="Search Claude Code session transcripts.")
    parser.add_argument("query", nargs="?", help="regex; falls back to literal")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--max", type=int, default=DEFAULT_MAX, dest="max_hits")
    parser.add_argument("--list-roots", action="store_true")
    args = parser.parse_args()

    roots = discover_roots()
    if not roots:
        sys.stderr.write(
            "gl-recall: no transcript root found. Searched:\n" +
            "".join("  %s\n" % p for p in searched_paths()) +
            "Set CLAUDE_TRANSCRIPT_DIR to the directory holding your .jsonl "
            "session files and run again.\n")
        return 1

    if args.list_roots:
        for root in roots:
            count = sum(1 for _ in root.rglob("*.jsonl"))
            print("%s  (%d transcript(s))" % (root, count))
        return 0

    if not args.query:
        parser.error("a query is required unless --list-roots is given")

    pattern = build_pattern(args.query)
    hits = 0
    sessions = 0
    for mtime, path in transcripts(roots, args.days):
        if hits >= args.max_hits:
            break
        session_hits = []
        for role, text in records(path):
            for match in pattern.finditer(text):
                session_hits.append((role, window(text, match)))
                break                     # one snippet per record keeps it readable
            if hits + len(session_hits) >= args.max_hits:
                break
        if not session_hits:
            continue
        room = args.max_hits - hits
        session_hits = session_hits[:room]
        sessions += 1
        hits += len(session_hits)
        stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
        print("\n%s (%s)" % (path.stem, stamp))
        print("-" * (len(path.stem) + len(stamp) + 3))
        for role, snippet in session_hits:
            print("  %s: %s" % (role, snippet))

    print("\n%d match(es) across %d session(s)" % (hits, sessions))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
```

- [ ] **Step 4: Make it executable and run the tests**

```bash
chmod +x growth-loop/bin/gl-recall
python3 -m py_compile growth-loop/bin/gl-recall
python3 tests/run.py
```

Expected: every `TestRecall` case PASSES and the whole suite is green.

- [ ] **Step 5: Commit**

```bash
git add growth-loop/bin/gl-recall tests/test_recall.py
git commit -m "feat: add gl-recall deterministic transcript search"
```

---

### Task 3: `bin/gl-nudge` — session-weight heuristic, cooldown, ledger

**Files:**
- Create: `growth-loop/bin/gl-nudge`
- Test: `tests/test_nudge.py`

**Interfaces:**
- Consumes: `fixtures.run`, `fixtures.tmpdir`, `fixtures.write_transcript`, `fixtures.hook_payload`.
- Produces: reads hook JSON on stdin, writes `$GROWTH_LOOP_HOME/ledger.jsonl` (one JSON object per line: `{"ts": <float>, "session": <str>, "stats": {"tool_calls": int, "edits": int, "files": [str]}}`) and `$GROWTH_LOOP_HOME/nudge-state.json` (`{"last_nudge": <float>, "last_session": <str>}`). Always exits 0.

- [ ] **Step 1: Write the failing test**

Create `tests/test_nudge.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 tests/run.py`
Expected: FAIL — `gl-nudge` does not exist.

- [ ] **Step 3: Implement `gl-nudge`**

Create `growth-loop/bin/gl-nudge`:

```python
#!/usr/bin/env python3
"""Advisory persistence nudge for Stop and SessionEnd.

An alert that always fires is wallpaper. The thresholds and the cooldown are
the feature, not plumbing: the failure mode of this whole plugin is a nudge
the operator learns to ignore.

This hook never blocks. It exits 0 on every path, including every failure.
"""
import json
import os
import sys
import time
from pathlib import Path

# --- Tunable constants. Start conservative; loosen only if you find yourself
# --- wishing the nudge had fired. Tightening after habituation does not work.
MIN_TOOL_CALLS = 25          # a session lighter than this rarely holds a skill
MIN_EDITS = 3                # reading is not doing; require real mutation
COOLDOWN_SECONDS = 6 * 3600  # at most one nudge per 6h, shared by both events
EDIT_MARKERS = ("edit", "write", "create", "str_replace")

DEFAULT_HOME = "~/.claude/growth-loop"


def home():
    return Path(os.environ.get("GROWTH_LOOP_HOME", DEFAULT_HOME)).expanduser()


def measure(path):
    """Return (tool_calls, edits, [file_path, ...]) from a transcript."""
    calls = edits = 0
    files = []
    try:
        handle = open(path, "r", encoding="utf-8", errors="replace")
    except OSError:
        return 0, 0, []
    with handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except (ValueError, TypeError):
                continue
            if not isinstance(rec, dict):
                continue
            message = rec.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                calls += 1
                name = str(block.get("name", "")).lower()
                if any(marker in name for marker in EDIT_MARKERS):
                    edits += 1
                    payload = block.get("input")
                    target = payload.get("file_path") if isinstance(payload, dict) else None
                    if target and target not in files:
                        files.append(target)
    return calls, edits, files


def read_state():
    try:
        return json.loads((home() / "nudge-state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def record(session_id, calls, edits, files):
    """Append to the ledger and stamp the cooldown. Never raises."""
    now = time.time()
    try:
        base = home()
        base.mkdir(parents=True, exist_ok=True)
        with open(base / "ledger.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": now,
                "session": session_id,
                "stats": {"tool_calls": calls, "edits": edits, "files": files},
            }) + "\n")
        (base / "nudge-state.json").write_text(
            json.dumps({"last_nudge": now, "last_session": session_id}),
            encoding="utf-8")
    except OSError:
        pass


def message(calls, edits, files):
    shown = ", ".join(Path(f).name for f in files[:4])
    if len(files) > 4:
        shown += ", +%d more" % (len(files) - 4)
    return (
        "This session ran %d tool calls with %d edits across %d file(s) (%s). "
        "That is enough weight that something in it may be worth keeping: a "
        "procedure that took real work to get right belongs in "
        "/growth-loop:learn, and a durable fact about how this person works "
        "belongs in /growth-loop:profile. If it was routine, say nothing and "
        "move on." % (calls, edits, len(files), shown)
    )


def main():
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        return 0
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return 0
    if not isinstance(payload, dict):
        return 0

    transcript = payload.get("transcript_path")
    session_id = payload.get("session_id") or "unknown"
    event = payload.get("hook_event_name") or "Stop"
    if not transcript or not Path(transcript).is_file():
        return 0

    if time.time() - float(read_state().get("last_nudge", 0) or 0) < COOLDOWN_SECONDS:
        return 0

    calls, edits, files = measure(transcript)
    if calls < MIN_TOOL_CALLS or edits < MIN_EDITS:
        return 0

    record(session_id, calls, edits, files)
    text = message(calls, edits, files)

    if event == "SessionEnd":
        # SessionEnd has no next model call, and its stdout does not reach
        # Claude. Address the human instead.
        print(json.dumps({"systemMessage": text}))
    else:
        # Stop, exit 0 with JSON: additionalContext reaches Claude as a system
        # reminder on the next model call. Never `decision: block` — a nudge
        # that hijacks control is not a nudge, and it burns the block cap.
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": text,
        }}))
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception:      # a hook must never break a session
        pass
    sys.exit(0)
```

- [ ] **Step 4: Make it executable and run the tests**

```bash
chmod +x growth-loop/bin/gl-nudge
python3 -m py_compile growth-loop/bin/gl-nudge
python3 tests/run.py
```

Expected: every `TestNudge` case PASSES.

- [ ] **Step 5: Commit**

```bash
git add growth-loop/bin/gl-nudge tests/test_nudge.py
git commit -m "feat: add gl-nudge advisory persistence nudge"
```

---

### Task 4: `bin/gl-journey` — asset inventory with staleness

**Files:**
- Create: `growth-loop/bin/gl-journey`
- Test: `tests/test_journey.py`

**Interfaces:**
- Consumes: `fixtures.run`, `fixtures.tmpdir`, `fixtures.write_skill`.
- Produces: CLI contract `gl-journey [--stale N] [--home PATH]`. Exit 0 always. Sections in order: `SKILLS`, `MEMORY`, `LEDGER`, then a closing review prompt. Honours `GROWTH_LOOP_SKILL_ROOTS` (`os.pathsep`-separated) for testability.

- [ ] **Step 1: Write the failing test**

Create `tests/test_journey.py`:

```python
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
            env["GROWTH_LOOP_SKILL_ROOTS"] = "%s:%s" % (self.skills, link_root / "alias")
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 tests/run.py`
Expected: FAIL — `gl-journey` does not exist.

- [ ] **Step 3: Implement `gl-journey`**

Create `growth-loop/bin/gl-journey`:

```python
#!/usr/bin/env python3
"""Inventory every asset the learning loop has produced, with staleness.

A store that only grows becomes untrustworthy. This is the input to the
review that decides what stays.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

SKILL_ROOTS = ("~/.claude/skills", "~/.claude/plugins", "./.claude/skills")
MEMORY_FILES = ("~/.claude/CLAUDE.md", "./CLAUDE.md")
STALE_DAYS = 90              # tunable: age at which a skill needs a verdict
DEFAULT_HOME = "~/.claude/growth-loop"
DESC_CHARS = 90


def home():
    return Path(os.environ.get("GROWTH_LOOP_HOME", DEFAULT_HOME)).expanduser()


def skill_roots():
    override = os.environ.get("GROWTH_LOOP_SKILL_ROOTS")
    sources = override.split(os.pathsep) if override else SKILL_ROOTS
    return [Path(s).expanduser() for s in sources if s]


def age_days(path):
    try:
        return (time.time() - path.stat().st_mtime) / 86400.0
    except OSError:
        return 0.0


def description_of(path):
    """Pull the description: line out of YAML frontmatter."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "(unreadable)"
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "(no frontmatter)"
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.lower().startswith("description:"):
            return line.split(":", 1)[1].strip().strip("\"'") or "(empty)"
    return "(no description)"


def collect_skills():
    found, seen = [], set()
    for root in skill_roots():
        if not root.is_dir():
            continue
        try:
            paths = sorted(root.rglob("SKILL.md"))
        except OSError:
            continue
        for path in paths:
            try:
                key = str(path.resolve())
            except OSError:
                continue
            if key in seen:
                continue
            seen.add(key)
            found.append((path.parent.name, path, age_days(path)))
    found.sort(key=lambda item: item[2], reverse=True)   # oldest first
    return found


def main():
    parser = argparse.ArgumentParser(
        description="Inventory skills and memory produced by the learning loop.")
    parser.add_argument("--stale", type=int, default=None,
                        help="show only assets older than N days")
    args = parser.parse_args()

    print("SKILLS")
    print("=" * 6)
    shown = 0
    for name, path, age in collect_skills():
        if args.stale is not None and age < args.stale:
            continue
        shown += 1
        flag = "STALE " if age >= STALE_DAYS else "      "
        desc = description_of(path)
        if len(desc) > DESC_CHARS:
            desc = desc[:DESC_CHARS - 3] + "..."
        print("%s%-28s %5s  %s" % (flag, name, "%dd" % int(age), desc))
    if shown == 0:
        print("  (none)")

    print("\nMEMORY")
    print("=" * 6)
    targets = [Path(m).expanduser() for m in MEMORY_FILES] + [home() / "profile.md"]
    for target in targets:
        try:
            stat = target.stat()
        except OSError:
            continue
        print("  %-52s %5s  %d bytes"
              % (target, "%dd" % int(age_days(target)), stat.st_size))

    print("\nLEDGER")
    print("=" * 6)
    try:
        count = sum(1 for line in
                    (home() / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
                    if line.strip())
    except OSError:
        count = 0
    print("  %d nudge(s) recorded in %s" % (count, home() / "ledger.jsonl"))

    print("\nStale means one of two things and you have to say which: finished "
          "work to delete, or drifted knowledge to re-verify. A skill that has "
          "never been invoked is usually the former.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
```

- [ ] **Step 4: Make it executable and run the tests**

```bash
chmod +x growth-loop/bin/gl-journey
python3 -m py_compile growth-loop/bin/gl-journey
python3 tests/run.py
```

Expected: every `TestJourney` case PASSES.

- [ ] **Step 5: Commit**

```bash
git add growth-loop/bin/gl-journey tests/test_journey.py
git commit -m "feat: add gl-journey asset inventory"
```

---

### Task 5: `hooks/hooks.json` and the constraints guard

**Files:**
- Create: `growth-loop/hooks/hooks.json`
- Test: `tests/test_constraints.py` (also covers the `bin/` scripts from Tasks 2–4)

**Interfaces:**
- Consumes: `fixtures.PLUGIN_ROOT`, `fixtures.BIN`.
- Produces: the hook registration Claude Code loads. Both `Stop` and `SessionEnd` point at `"${CLAUDE_PLUGIN_ROOT}"/bin/gl-nudge`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_constraints.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 tests/run.py`
Expected: FAIL — `hooks/hooks.json` does not exist. (`TestScriptConstraints` should already pass.)

- [ ] **Step 3: Write the hook registration**

Create `growth-loop/hooks/hooks.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"${CLAUDE_PLUGIN_ROOT}\"/bin/gl-nudge"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"${CLAUDE_PLUGIN_ROOT}\"/bin/gl-nudge"
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 4: Run the tests**

Run: `python3 tests/run.py`
Expected: every `TestHooks` and `TestScriptConstraints` case PASSES.

- [ ] **Step 5: Commit**

```bash
git add growth-loop/hooks/hooks.json tests/test_constraints.py
git commit -m "feat: register gl-nudge on Stop and SessionEnd"
```

---

### Task 6: `learn`, `refine`, and the `skill-author` subagent

**Files:**
- Create: `growth-loop/skills/learn/SKILL.md`, `growth-loop/skills/refine/SKILL.md`, `growth-loop/agents/skill-author.md`
- Test: `tests/test_skills.py`

**Interfaces:**
- Consumes: `fixtures.PLUGIN_ROOT`, `fixtures.MODEL_INVOKED`, `fixtures.USER_INVOKED_ONLY`.
- Produces: `tests/test_skills.py` with `parse_frontmatter(path) -> (dict, str)`, reused by Tasks 7 and 8. The linter runs over whichever SKILL.md files exist, so it stays green as skills are added.

**Shared writing standards (§5.2) — these apply to every SKILL.md in Tasks 6–8 and are restated *inside* `learn` and `skill-author` as the standards for the skills the loop later generates:**

- Description = what + when, third person, concrete triggers. Claude measurably under-triggers skills, so be slightly assertive and name the exact situation.
- Verbatim commands. "Run the migration" is useless; the exact invocation with the flags that mattered is the skill.
- The failures are the payload. Any model reproduces the happy path from first principles; what it cannot reconstruct is which plausible approach silently fails and how that was recognised. A distillation with no dead end is not worth writing.
- No hedging. A step that "might work" has not been written yet. If uncertainty is the finding, state it as a finding with a check command.
- Length follows content. Fifteen lines is a fine skill; padding lowers signal-to-context.
- Declining is the default. Most sessions do not deserve a skill; each skill must say so and make "write nothing" a first-class outcome.

- [ ] **Step 1: Write the failing linter test**

Create `tests/test_skills.py`:

```python
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
        self.assertIn("gl-journey", self.body)
        self.assertIn("/growth-loop:refine", self.body)

    def test_states_the_three_way_gate(self):
        for gate in ("took real work", "will recur", "procedural"):
            self.assertIn(gate, self.body)

    def test_carries_the_output_template(self):
        for heading in ("When this applies", "The approach", "What goes wrong"):
            self.assertIn(heading, self.body)

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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 tests/run.py`
Expected: FAIL — `AssertionError`/`FileNotFoundError` on `skills/learn/SKILL.md`.

- [ ] **Step 3: Write `skills/learn/SKILL.md`**

Frontmatter, verbatim:

```yaml
---
name: learn
description: Distils a reusable skill from work that just finished, when a task took real effort to get right and the same problem will come back. Use when the user says "remember how to do this", "write that down", or "make a skill for this"; when a multi-step procedure has just succeeded after several failed attempts; or when the nudge hook reports a heavy session. Takes an optional target - a directory or URL - and otherwise distils this conversation.
argument-hint: "[directory-or-url]"
---
```

Body sections, in this order, each written to the §5.2 standards above:

1. **`## First: check for overlap`** — run `` gl-journey `` verbatim before anything else. If an existing skill covers the same ground, stop and route to `/growth-loop:refine` instead. State the reason plainly: near-duplicates are the rot vector, because two skills describing the same procedure differently means neither can be trusted.
2. **`## The gate`** — all three must hold or nothing gets written: it **took real work** to figure out (not reconstructible from first principles), it **will recur**, and it is **procedural** (a way of doing, not a fact about one repo — facts belong in CLAUDE.md, facts about the person belong in `/growth-loop:profile`).
3. **`## When to write nothing`** — most sessions do not deserve a skill. Say "nothing here is worth keeping" and stop; that is a success, not a failure. Name the common false positives: a task that only felt hard because of an outage, a one-off migration, anything already in the project's CLAUDE.md.
4. **`## Where it goes`** — `~/.claude/skills/<slug>/SKILL.md`, slug in kebab-case. Written outside the plugin on purpose so it survives the plugin being removed.
5. **`## The template`** — reproduce it literally in a fenced block:
   ```markdown
   ---
   name: <slug>
   description: <what it does + the exact situation that should trigger it>
   ---

   ## When this applies
   ## The approach
   ## What goes wrong
   ```
   Then the per-section rules: **The approach** carries verbatim commands with the flags that mattered — "run the migration" is useless. **What goes wrong** is the payload: which plausible route silently fails, and the symptom that identified it. A distillation with no dead end is not worth writing; if you cannot name one, go back to the gate.
6. **`## Delegating`** — if the session is long, dispatch the `skill-author` subagent instead of writing inline, to keep distillation out of the main session's context. Give it the facts; it writes the document.
7. **`## Reporting`** — afterwards report only two things: the path, and the description line. Do not paste the skill back into the conversation.
8. **`## Handling $ARGUMENTS`** — `$ARGUMENTS` empty means distil this conversation; a directory means read it and distil the procedure it encodes; a URL means fetch and distil. Same gate applies to all three.

- [ ] **Step 4: Write `skills/refine/SKILL.md`**

Frontmatter, verbatim:

```yaml
---
name: refine
description: Corrects a stored skill the moment it proves wrong in use - a step that failed, an assumption that no longer holds, a better route found, or a description that fired at the wrong time. Use when following a skill produced an error, when a documented command no longer exists, or when the right skill did not fire for an obviously matching task. Correct at failure time, never as a retrospective.
---
```

Body sections:

1. **`## When this fires`** — the four triggers named in the description, plus the hard rule: only on something that happened **this session**. Never refine on a hunch. The correction is worth writing exactly when the error is fully understood, which is now, not later.
2. **`## The procedure`** — Read the whole file first, before editing any of it; a targeted edit to a file you have not read produces contradictions between sections. Then make the smallest correct edit. Then append a dated entry under `## Revisions` stating what changed **and why** — the why is what stops the next reader from re-introducing the old step.
3. **`## Fixing the description`** — if the failure was *targeting* (the skill did not fire, or fired on the wrong task), the body is fine and the description is the bug. Rewrite it to name the situation that just occurred.
4. **`## What not to do`** — never soften a wrong step into a hedge. "This may not work on newer versions" is not a correction; it is a wrong step with a disclaimer, and it costs a reader the same time as the original error. Either state the condition precisely or delete the step.
5. **`## When it is beyond repair`** — if more than half the skill is wrong, stop editing and route to `/growth-loop:forget`. **Beyond repair is a real verdict.** A heavily patched skill built on a dead assumption reads as authoritative and is not.
6. **`## When to write nothing`** — a skill that was merely unhelpful, not wrong, needs no edit. Do not churn.

- [ ] **Step 5: Write `agents/skill-author.md`**

Frontmatter, verbatim:

```yaml
---
name: skill-author
description: Writes a SKILL.md document from facts supplied by the main session. Use when distillation would otherwise consume the main session's context. Writes the document and nothing else.
tools: Read, Write, Edit, Glob, Grep, Bash
---
```

Body:

1. **Persona, stated first and bluntly:** you write skill documents. You do not solve the underlying problem, do not improve the approach you were handed, and do not opine on whether it was the right approach. If the approach was wrong, that belongs in the caller's hands, not in the document.
2. **The standards** — restate the §5.2 list in full (description = what + when with concrete triggers; verbatim commands; the failures are the payload; no hedging; length follows content).
3. **`What goes wrong` is mandatory.** If the facts you were given contain no dead end, do not invent one and do not write the skill — report back that the material does not support a skill.
4. **Write the description line last**, after the body exists, so it describes what is actually in the document rather than what was planned.
5. **Report exactly two things:** the path written, and the description line. Nothing else.

- [ ] **Step 6: Run the tests**

Run: `python3 tests/run.py`
Expected: every `TestSkillFrontmatter`, `TestLearn`, `TestRefine`, `TestSkillAuthorAgent` case PASSES.

- [ ] **Step 7: Commit**

```bash
git add growth-loop/skills/learn growth-loop/skills/refine growth-loop/agents tests/test_skills.py
git commit -m "feat: add learn and refine skills with skill-author subagent"
```

---

### Task 7: `recall` and `profile`

**Files:**
- Create: `growth-loop/skills/recall/SKILL.md`, `growth-loop/skills/profile/SKILL.md`
- Modify: `tests/test_skills.py` (append two test classes)

**Interfaces:**
- Consumes: `parse_frontmatter` from Task 6.
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_skills.py`:

```python
class TestRecall(unittest.TestCase):
    def setUp(self):
        self.meta, self.body = parse_frontmatter(
            PLUGIN_ROOT / "skills" / "recall" / "SKILL.md")

    def test_runs_gl_recall(self):
        self.assertIn("gl-recall", self.body)

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

    def test_names_the_file(self):
        self.assertIn("~/.claude/growth-loop/profile.md", self.body)

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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 tests/run.py`
Expected: FAIL — `skills/recall/SKILL.md` does not exist.

- [ ] **Step 3: Write `skills/recall/SKILL.md`**

Frontmatter, verbatim:

```yaml
---
name: recall
description: Recovers context from past Claude Code sessions by searching transcripts. Use when the user refers to earlier work without restating it - "how did we fix that", "what was the workaround", "we decided something about this" - or when a task resumes and the reasoning behind the current state is not in context. Searches deterministically outside the model, then summarises.
argument-hint: "[what to search for]"
---
```

Body sections:

1. **`## Search`** — run `gl-recall "<query>"` (verbatim). Start with the user's own words; add `--days 365` when the memory is old. On thin results, widen with the concrete strings that would actually appear in a transcript: error text, filenames, command names — not paraphrases.
2. **`## Reading the hits`** — **newest session first**; a later session usually supersedes an earlier one. Prefer the **resolution** over the discussion around it: what was *decided* outranks what was merely *considered*, and a transcript contains far more of the latter. Watch for the pattern where an approach is discussed at length and then abandoned in one line.
3. **`## Answering`** — answer the user's actual question, **conclusion first**, then the supporting detail. Never dump raw `gl-recall` output into the conversation; that spends the context this tool exists to protect.
4. **`## When nothing is found`** — check `gl-recall --list-roots`. If it reports no root, say so and give the remedy: set `CLAUDE_TRANSCRIPT_DIR` to the directory holding the `.jsonl` session files. Do not report "no history" when the real problem is that no history was searched.
5. **`## Close the loop`** — a fact that had to be **searched twice** should not need a third search. Recall is the fallback; persistence is the fix. Route project facts to CLAUDE.md and facts about the person to `/growth-loop:profile`.

- [ ] **Step 4: Write `skills/profile/SKILL.md`**

Frontmatter, verbatim:

```yaml
---
name: profile
description: Maintains a cross-project model of the person at ~/.claude/growth-loop/profile.md - their tooling, conventions, and working style. Use when a stated preference recurs for the second time, when the user corrects the same class of thing again, or when the nudge hook reports a heavy session. CLAUDE.md describes the project; this describes the person and travels between repos.
---
```

Body sections:

1. **`## The file`** — `~/.claude/growth-loop/profile.md`, or `$GROWTH_LOOP_HOME/profile.md` when that is set. It sits outside any repository on purpose: the person travels between repos and the project does not.
2. **`## The test`** — every line must pass both halves: still true in three months, and still true in a different repository. A line that fails either belongs in CLAUDE.md instead.
3. **`## Sections`** — exactly three: `## Tooling`, `## Conventions`, `## Working style`. Every line carries the date it was written, as `(YYYY-MM-DD)`.
4. **`## Before writing`** — read the file first. One instance is a data point; **the second occurrence is the pattern** that gets written. Writing on first sight produces a profile full of accidents.
5. **`## Superseding`** — never silently overwrite. Carry the history: `uses pnpm (previously npm) (2026-08-04)`. The previous value is what stops a future session from re-suggesting it.
6. **`## Size`** — cap at about 60 lines. When it grows past that, age out the entries that were never reinforced — an unreinforced line is a guess that survived by inertia.
7. **`## What never goes in`** — health, finances, relationships, politics. Anything **inferred** rather than stated. Omit it entirely; never write a vague placeholder in its place, because a placeholder still directs behaviour without evidence.
8. **`## Refusing`** — decline to persist instructions that would make future sessions **less honest**: "always agree", "skip the risk caveats", "do not mention downsides". Say so in conversation and store nothing.
9. **`## When to write nothing`** — most sessions add no line. A profile that grows every session is recording noise.
10. **`## Never announce the write.`** State it as its own line.

- [ ] **Step 5: Run the tests**

Run: `python3 tests/run.py`
Expected: `TestRecall` and `TestProfile` PASS.

- [ ] **Step 6: Commit**

```bash
git add growth-loop/skills/recall growth-loop/skills/profile tests/test_skills.py
git commit -m "feat: add recall and profile skills"
```

---

### Task 8: `journey` and `forget`

**Files:**
- Create: `growth-loop/skills/journey/SKILL.md`, `growth-loop/skills/forget/SKILL.md`
- Modify: `tests/test_skills.py` (append two test classes)

**Interfaces:**
- Consumes: `parse_frontmatter` from Task 6.
- Produces: nothing later tasks depend on. These two are the only skills with `disable-model-invocation: true`; `test_invocation_flags` from Task 6 starts enforcing it here.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_skills.py`:

```python
class TestJourneySkill(unittest.TestCase):
    def setUp(self):
        self.meta, self.body = parse_frontmatter(
            PLUGIN_ROOT / "skills" / "journey" / "SKILL.md")

    def test_is_user_invoked_only(self):
        self.assertEqual(self.meta.get("disable-model-invocation"), "true")

    def test_runs_both_journey_invocations(self):
        self.assertIn("gl-journey", self.body)
        self.assertIn("--stale 60", self.body)

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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 tests/run.py`
Expected: FAIL — `skills/journey/SKILL.md` does not exist.

- [ ] **Step 3: Write `skills/journey/SKILL.md`**

Frontmatter, verbatim:

```yaml
---
name: journey
description: Reviews everything the learning loop has accumulated - skills, memory files, the nudge ledger - and forces a verdict on each stale item. Run this deliberately, about monthly, or when the skill library has grown past the point where you can name what is in it. Review is a human decision, so this skill is never invoked automatically.
disable-model-invocation: true
---
```

Body sections:

1. **`## Gather`** — run `gl-journey`, then `gl-journey --stale 60` (both verbatim).
2. **`## The verdict`** — every stale item gets exactly one of three, and **no undecided leftovers**:
   - **delete** — route to `/growth-loop:forget`;
   - **verify and correct** — check it against reality now, then route to `/growth-loop:refine`;
   - **keep and say so** — state why it is still right despite the age.
   "I'll look at it later" is not one of the three. An item you cannot decide on is an item nobody trusts, which is the same as deleted but with the context cost still being paid.
3. **`## Duplicates`** — hunt for skills covering the same ground. Merge into the one with the better **What goes wrong** section, not the newer one: the dead ends are the irreplaceable part.
4. **`## Audit the description set`** — read the descriptions together, as a set, not one at a time. The question is: given a task, **would exactly the right one fire**? Overlapping descriptions mean the wrong skill fires; vague ones mean none does.
5. **`## Report`** — a short verdict, **not the inventory**. The user already ran the inventory; what they need is the decisions.

- [ ] **Step 4: Write `skills/forget/SKILL.md`**

Frontmatter, verbatim:

```yaml
---
name: forget
description: Deletes a skill or a profile entry completely, after showing exactly what will be removed and getting confirmation. Use when the user says "forget that", "delete that skill", or "that is no longer true". Deletion is a human decision, so this skill is never invoked automatically.
argument-hint: "[what to forget]"
disable-model-invocation: true
---
```

Body sections:

1. **`## Locate`** — resolve `$ARGUMENTS` to a concrete target. Run `gl-journey` if the reference is by topic rather than name. Where the scope is **ambiguous** — several matches, or unclear whether the user means a skill or a profile line — ask before touching anything.
2. **`## Show`** — print exactly what will be removed: the full path for a skill directory, the literal line for a profile entry. Not a summary of it.
3. **`## Confirm`** — **Wait for confirmation.** Do not proceed on an implied yes.
4. **`## Delete`** — a skill means the whole `<slug>/` directory, including its supporting files. A profile entry means that line, removed from the file.
5. **`## Delete, do not soften`** — no `[deprecated]` markers, no "this may no longer apply", no commented-out blocks. A tombstone is ambiguous context that still loads every single session and still shapes behaviour; it costs what the original cost and returns nothing. Genuine supersession is a `/growth-loop:profile` update carrying the old value forward. The word *forget* means gone.
6. **`## Follow the references`** — remove **derived** entries that depended on the deleted item: profile lines that only made sense alongside it, other skills whose bodies point at it.

- [ ] **Step 5: Run the tests**

Run: `python3 tests/run.py`
Expected: `TestJourneySkill` and `TestForget` PASS; `test_invocation_flags` now passes with real assertions on both files.

- [ ] **Step 6: Commit**

```bash
git add growth-loop/skills/journey growth-loop/skills/forget tests/test_skills.py
git commit -m "feat: add journey and forget skills"
```

---

### Task 9: README, synthetic end-to-end verification, acceptance

**Files:**
- Create: `growth-loop/README.md`, `tests/test_completeness.py`
- Test: full suite + the spec §7 protocol run by hand

**Interfaces:**
- Consumes: everything, including `fixtures.EXPECTED_TREE`.
- Produces: the finished plugin.

- [ ] **Step 0: Write the completeness test**

Create `tests/test_completeness.py` — the single assertion that the plugin tree matches spec §4 exactly. It belongs here, at the end, because it is only meaningful once every file exists:

```python
import unittest

from fixtures import EXPECTED_TREE, PLUGIN_ROOT


class TestCompleteness(unittest.TestCase):
    def test_tree_is_exactly_the_thirteen_files(self):
        found = {
            str(p.relative_to(PLUGIN_ROOT))
            for p in PLUGIN_ROOT.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
        }
        missing = sorted(set(EXPECTED_TREE) - found)
        unexpected = sorted(found - set(EXPECTED_TREE))
        self.assertEqual((missing, unexpected), ([], []))

    def test_there_are_exactly_thirteen(self):
        self.assertEqual(len(EXPECTED_TREE), 13)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 1: Write `growth-loop/README.md`**

Required content, in this order:

1. **What it adds** — one paragraph, then a command table:

   | Command | Invoked by | Does |
   |---|---|---|
   | `/growth-loop:learn [target]` | Claude or you | Distils a skill from work that just finished |
   | `/growth-loop:refine` | Claude or you | Corrects a skill the moment it proves wrong |
   | `/growth-loop:recall [query]` | Claude or you | Recovers reasoning from past sessions |
   | `/growth-loop:profile` | Claude or you | Maintains the cross-project model of you |
   | `/growth-loop:journey` | **you only** | Monthly review with forced verdicts |
   | `/growth-loop:forget [target]` | **you only** | Deletes completely, after confirmation |

   State why the split exists: review and deletion are human decisions.

2. **Non-goals** — reproduce the OUT-row table from spec §1 (cron/scheduling, subagents, chat surfaces, terminal backends, MCP, compress/undo/retry, image/video/TTS) with the built-in that covers each, and the rationale: duplicating a built-in produces two half-working systems.

3. **Install:**

```bash
git clone <repo> growth-loop
chmod +x growth-loop/bin/*        # required — the Stop hook depends on it
claude --plugin-dir ./growth-loop
```

   Note the alternative: `claude plugin init` scaffolds into `~/.claude/skills/<name>/`, which autoloads as `<name>@skills-dir` with no install step. After changing plugin files in a running session, run `/reload-plugins`.

4. **Verify:**

```bash
claude plugin validate ./growth-loop   # manifest + frontmatter + hooks schema
gl-recall --list-roots                 # must print at least one root
gl-journey                             # inventory
```
   `/hooks` should show `gl-nudge` on both `Stop` and `SessionEnd`. If `gl-recall --list-roots` finds nothing, set `CLAUDE_TRANSCRIPT_DIR` to the directory holding your `.jsonl` session files.

5. **Layout** — the §4 tree, plus: state lives in `~/.claude/growth-loop/` (`profile.md`, `ledger.jsonl`, `nudge-state.json`), overridable with `GROWTH_LOOP_HOME`. Distilled skills are written to `~/.claude/skills/<slug>/SKILL.md` so they load globally and survive this plugin being removed.

6. **Tuning** — the table below, with the warning that these defaults are deliberately conservative: **the failure mode of this plugin is a nudge you learn to ignore.** Loosen only after you find yourself wishing it had fired; tightening after habituation does not undo it.

   | Constant | File | Default | Meaning |
   |---|---|---|---|
   | `MIN_TOOL_CALLS` | `bin/gl-nudge` | 25 | Minimum tool calls before the nudge fires |
   | `MIN_EDITS` | `bin/gl-nudge` | 3 | Minimum mutating calls — reading is not doing |
   | `COOLDOWN_SECONDS` | `bin/gl-nudge` | 21600 | At most one nudge per 6h, shared by both events |
   | `STALE_DAYS` | `bin/gl-journey` | 90 | Age at which an asset needs a verdict |
   | `SNIPPET_CHARS` | `bin/gl-recall` | 400 | Window around each transcript match |

7. **Design notes** — condensed §6: skill-library-from-execution (Voyager); negative knowledge is the moat, hence the mandatory *What goes wrong*; reflect-at-failure-time (Reflexion), hence `refine` fires during the task; memory needs curation not accumulation (Generative Agents, MemGPT), hence `journey`/`forget` are first-class and deletion means deletion; progressive disclosure, hence search lives in `bin/` and the model only summarises; the person travels between repos and the project does not, hence `profile.md` sits outside any repository.

8. **Hook delivery** — document the verified asymmetry: on `Stop`, exit 0 with `hookSpecificOutput.additionalContext` reaches Claude as a system reminder on the next model call. On `SessionEnd`, hook stdout does not reach Claude and there is no next model call, so the nudge is delivered as a user-facing `systemMessage` there. The hook never uses exit 2 or `decision: block` on `Stop` — that would force the agent to continue and burn the consecutive-block cap. It exits 0 in every path.

9. **Usage limits and compliance** — verbatim in spirit: everything runs inside the official Claude Code harness; no OAuth token is read, extracted, proxied, or passed anywhere, because routing subscription credentials through third-party tools is prohibited. Advertised Pro and Max limits assume ordinary, individual use of Claude Code and the Agent SDK, so nothing here encourages or enables unattended 24/7 operation — this plugin is for interactive sessions. `bin/` is Python 3 stdlib only: no pip installs, no network calls, no telemetry.

- [ ] **Step 2: Run the full suite**

```bash
python3 -m py_compile growth-loop/bin/gl-recall growth-loop/bin/gl-nudge growth-loop/bin/gl-journey
python3 -c "import json,pathlib; [json.loads(pathlib.Path(p).read_text()) for p in ['growth-loop/.claude-plugin/plugin.json','growth-loop/hooks/hooks.json']]; print('json ok')"
ls -l growth-loop/bin/
python3 tests/run.py
```

Expected: `json ok`, all three scripts `-rwxr-xr-x`, and the **entire suite green, including the new `TestCompleteness`**.

- [ ] **Step 3: Synthetic end-to-end in a scratch dir (spec §7.3)**

```bash
SCRATCH=$(mktemp -d)
mkdir -p "$SCRATCH/projects/fakerepo" "$SCRATCH/home" "$SCRATCH/skills/planted-skill"
python3 - "$SCRATCH" <<'PY'
import json, sys
from pathlib import Path
scratch = Path(sys.argv[1])
t = scratch / "projects" / "fakerepo" / "sess-e2e.jsonl"
lines = [
  {"type":"user","message":{"role":"user","content":[{"type":"text","text":"the deploy failed with ECONNREFUSED"}]}},
  {"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Fixed by pointing DATABASE_URL at the socket."}]}},
]
paths = ["/r/a.py", "/r/b.py", "/r/c.py", "/r/d.py"]
for i in range(30):
    lines.append({"type":"assistant","message":{"role":"assistant","content":[
        {"type":"tool_use","name":"Edit","id":"t%d"%i,"input":{"file_path":paths[i%4]}}]}})
t.write_text("\n".join(json.dumps(l) for l in lines) + "\n{ corrupt\n")
(scratch/"skills"/"planted-skill"/"SKILL.md").write_text(
    "---\nname: planted-skill\ndescription: A planted skill for the e2e check\n---\n\nBody.\n")
print(t)
PY

export CLAUDE_TRANSCRIPT_DIR="$SCRATCH"
export GROWTH_LOOP_HOME="$SCRATCH/home"
export GROWTH_LOOP_SKILL_ROOTS="$SCRATCH/skills"

./growth-loop/bin/gl-recall --list-roots
./growth-loop/bin/gl-recall ECONNREFUSED

PAYLOAD="{\"session_id\":\"e2e\",\"transcript_path\":\"$SCRATCH/projects/fakerepo/sess-e2e.jsonl\",\"cwd\":\"/tmp\",\"hook_event_name\":\"Stop\"}"
echo "$PAYLOAD" | ./growth-loop/bin/gl-nudge          # fires
echo "$PAYLOAD" | ./growth-loop/bin/gl-nudge          # silent (cooldown)

./growth-loop/bin/gl-journey
```

Expected, checked one by one:
- `--list-roots` prints `$SCRATCH` with `1 transcript(s)`.
- The query prints the user turn containing `ECONNREFUSED` and `1 match(es) across 1 session(s)`.
- First `gl-nudge` prints JSON containing `additionalContext` naming 30 calls, 30 edits, 4 files. Second prints **nothing**. Both exit 0.
- `gl-journey` lists `planted-skill` with `A planted skill for the e2e check`, and `1 nudge(s) recorded`.

```bash
unset CLAUDE_TRANSCRIPT_DIR GROWTH_LOOP_HOME GROWTH_LOOP_SKILL_ROOTS
rm -rf "$SCRATCH"
```

- [ ] **Step 4: Live load (spec §7.4)**

```bash
claude plugin validate ./growth-loop
claude --plugin-dir ./growth-loop
```

In the session: `/hooks` shows `gl-nudge` on both `Stop` and `SessionEnd`; `/growth-loop:journey` runs and produces verdicts; `/growth-loop:` autocompletes all six.

- [ ] **Step 5: Walk the acceptance checklist (spec §8)**

- [ ] 13 files, tree exactly as §4; nothing but `plugin.json` inside `.claude-plugin/` — proven by `tests/test_completeness.py` + `test_claude_plugin_dir_contains_only_the_manifest`
- [ ] All §3 facts re-verified against live docs; divergences reported — see the *Verified against live docs* table above; carry it into the final report
- [ ] Six skills meet §5.2; `journey`/`forget` user-invoked only — proven by `tests/test_skills.py`
- [ ] Nudge advisory-only, exit 0 everywhere, thresholds + cooldown proven by test — proven by `tests/test_nudge.py` + Step 3
- [ ] `gl-recall` root autodiscovery + env override + actionable empty state — proven by `tests/test_recall.py`
- [ ] No OUT-row feature; no network; no non-stdlib imports — proven by `tests/test_constraints.py`
- [ ] README contains the usage-limits note and the `chmod +x` requirement

- [ ] **Step 6: Commit**

```bash
git add growth-loop/README.md
git commit -m "docs: add README with install, verification, tuning and design notes"
```

- [ ] **Step 7: Report divergences**

Report to the operator: the four divergences from the *Verified against live docs* table (1,536-char description cap, Stop `additionalContext` delivery resolved, SessionEnd asymmetry, `plugin.json` now optional), plus the empirical transcript-root result on this machine, plus the confirmation that `claude-personality-learn` and `claude-transcript-organizer` do not overlap.

---

## Notes for the executor

- **Do not push.** Committing locally is in scope; pushing and PR creation require explicit approval.
- **`docs/superpowers/CURRENT.md`** should be created or updated through the session-handoff process after Task 9, not before.
- If any live-doc fact turns out to have changed since 2026-08-04, **the docs win** — adjust the implementation, note it, and tell the operator. Do not follow this plan against the docs.
- If a built-in turns out to cover part of an IN row, **shrink the scope** rather than duplicating it, and say what you found.
