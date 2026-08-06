"""Shared paths and fixture builders for the growth-loop test suite."""
import contextlib
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
    # Left ambient, this makes every gl-journey test depend on whatever the
    # operator has exported - including the fallback tests, which would then
    # assert a fallback they never exercised.
    environ.pop("GROWTH_LOOP_SKILL_ROOTS", None)
    if env:
        environ.update(env)
    proc = subprocess.run(
        [sys.executable, str(BIN / script)] + list(args),
        input=stdin, capture_output=True, text=True, env=environ,
    )
    return proc.returncode, proc.stdout, proc.stderr


SCRIPT_ENV_VARS = ("CLAUDE_TRANSCRIPT_DIR", "GROWTH_LOOP_HOME",
                   "GROWTH_LOOP_SKILL_ROOTS")


@contextlib.contextmanager
def clean_env():
    """Run a block with the scripts' env vars unset, then restore them.

    run() strips these for subprocesses. A function imported via
    load_script() runs in this process and reads os.environ when called, so
    it needs the same clean slate at call time — sanitising only around the
    import looks protective and is not.
    """
    saved = {k: os.environ.pop(k, None) for k in SCRIPT_ENV_VARS}
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value


def load_script(name):
    """Import a bin/ script as a module so its functions can be unit-tested.

    The scripts have no .py extension, and testing a pure function only
    through rendered CLI output hides regressions: a truncation marker
    dropped from clip() stayed invisible because a second code path emits
    the same characters.
    """
    import importlib.machinery
    import importlib.util
    # Executing the module writes a __pycache__ next to the script, which is
    # three extra files inside a plugin that must hold exactly thirteen.
    # test_completeness cannot catch it — discovery is alphabetical, so it
    # runs before this does. tests/run.py re-checks after the whole suite,
    # which is the backstop; this line is what prevents the damage.
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    # Sanitise for the import itself, in case a module ever reads the
    # environment at module level. This does NOT protect a function called
    # later — those read os.environ when called, not when imported. Use
    # clean_env() around the call for that.
    saved = {k: os.environ.pop(k, None) for k in SCRIPT_ENV_VARS}
    loader = importlib.machinery.SourceFileLoader(
        name.replace("-", "_"), str(BIN / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    try:
        loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value
    return module


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
