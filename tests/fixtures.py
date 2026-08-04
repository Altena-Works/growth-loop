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
                     tool_name="Edit", file_paths=None):
    """Write a synthetic JSONL transcript.

    Emits one user turn, one assistant text turn, then `tool_calls` tool_use
    blocks cycling through `file_paths`, then one deliberately corrupt line.

    `file_paths=None` (the default) stands in a placeholder path for every
    call, as if each one touched a file. Pass `file_paths=()` explicitly to
    model a tool whose input carries no `file_path` at all — e.g. TodoWrite,
    which mutates nothing.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        {"type": "user", "message": {"role": "user",
                                     "content": [{"type": "text", "text": user_text}]}},
        {"type": "assistant", "message": {"role": "assistant",
                                          "content": [{"type": "text", "text": assistant_text}]}},
    ]
    # This None/() distinction is load-bearing for
    # test_nudge.py::test_todowrite_does_not_count_as_an_edit, which needs
    # `file_paths=()` to mean "no file_path key at all" — if this line ever
    # goes back to falling back on an empty sequence, that test silently
    # stops testing anything (every TodoWrite call would carry a stand-in
    # file_path and count as an edit again).
    paths = list(file_paths) if file_paths is not None else ["/tmp/a.py"]
    for i in range(tool_calls):
        input_payload = {"old_string": "x", "new_string": "y"}
        if paths:
            input_payload = {"file_path": paths[i % len(paths)], **input_payload}
        lines.append({"type": "assistant", "message": {"role": "assistant", "content": [{
            "type": "tool_use", "name": tool_name, "id": "t%d" % i,
            "input": input_payload,
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
