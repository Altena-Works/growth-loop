#!/usr/bin/env python3
"""Opt-in behavioural harness: drives the real skills in real Claude Code
sessions and asserts only the observable consequences of a run.

    GROWTH_LOOP_E2E=1 python3 e2e/run_e2e.py [--case NAME]

See e2e/README.md for why this exists, why it is opt-in, and how to add a
case. In short: model output is nondeterministic, so this harness never
compares wording. It asserts things that do not change between runs of the
same case - which files exist afterwards, whether a directory was created or
left alone, whether a gate held, and whether a script another part of the
loop reads was actually reached.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

E2E_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = E2E_ROOT.parent
PLUGIN_DIR = PROJECT_ROOT / "growth-loop"
CASES_DIR = E2E_ROOT / "cases"
GL_JOURNEY = PLUGIN_DIR / "bin" / "gl-journey"

# A real model turn, not a subprocess call - 1-5 minutes is the observed
# range building this harness. Generous headroom beats a flaky timeout.
TIMEOUT_SECONDS = 600


class CaseFailure(Exception):
    """Carries exactly the one assertion that failed, and nothing else."""


def load_cases(only=None):
    paths = sorted(CASES_DIR.glob("*.json"))
    cases = []
    for path in paths:
        case = json.loads(path.read_text(encoding="utf-8"))
        case.setdefault("name", path.stem)
        if only and case["name"] != only:
            continue
        cases.append(case)
    return cases


def plant_skills(skills_root, specs):
    for spec in specs or []:
        slug = spec["slug"]
        skill_dir = skills_root / slug
        skill_dir.mkdir(parents=True, exist_ok=True)
        content = "---\nname: %s\ndescription: %s\n---\n\n%s\n" % (
            slug, spec["description"], spec.get("body", "N/A"))
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")


def skill_dir_names(skills_root):
    if not skills_root.is_dir():
        return set()
    return {p.parent.name for p in skills_root.glob("*/SKILL.md")}


def locate_skill(skills_root, home, slug):
    """Invoke the real, deterministic `gl-journey --locate` directly.

    This is not a second model call - gl-journey is plain Python with no
    model in the loop, so calling it straight is both faster and more
    reliable than spinning up a second session to ask a model to summarise
    what it sees. It reads the same GROWTH_LOOP_SKILL_ROOTS / GROWTH_LOOP_HOME
    env vars the skills resolve against, so this checks the exact thing that
    matters: does the script journey runs actually see what learn wrote.

    Deliberately `--locate <slug>`, not the plain listing: the plain listing
    clips the name column at NAME_CHARS (28) so it stays readable as a
    table, and a substring search for the full slug against that clipped
    output goes false-negative for any slug longer than that - which the
    first real run of this harness hit (a 29-character slug the model
    chose, clipped to "ci-cert-error-stale-ca-bu...") even though `learn`
    and `journey` agreed perfectly on where the skill lived. `--locate`
    exists for exactly this: name in, unclipped directory out, independent
    of column width.
    """
    env = dict(os.environ)
    env["GROWTH_LOOP_SKILL_ROOTS"] = str(skills_root)
    env["GROWTH_LOOP_HOME"] = str(home)
    proc = subprocess.run([sys.executable, str(GL_JOURNEY), "--locate", slug],
                          capture_output=True, text=True, env=env)
    return proc.returncode, proc.stdout


def invoke_claude(case, home, skills_root, workdir):
    env = dict(os.environ)
    env["GROWTH_LOOP_HOME"] = str(home)
    env["GROWTH_LOOP_SKILL_ROOTS"] = str(skills_root)
    cmd = [
        "claude", "--plugin-dir", str(PLUGIN_DIR), "-p",
        "--permission-mode", case.get("permission_mode", "acceptEdits"),
        "--add-dir", str(home),
        "--add-dir", str(skills_root),
        "--add-dir", str(workdir),
    ]
    allowed = case.get("allowed_tools")
    if allowed:
        cmd += ["--allowedTools"] + list(allowed)
    # The prompt MUST go on stdin. Passing a multi-line prompt as a trailing
    # argument fails outright ("Input must be provided either through stdin
    # or as a prompt argument") - measured, not guessed, while building this.
    return subprocess.run(
        cmd, cwd=str(workdir), input=case["prompt"], capture_output=True,
        text=True, env=env, timeout=TIMEOUT_SECONDS,
    )


def resolve(template, home, skills_root):
    return template.format(home=str(home), skills_root=str(skills_root))


def check(condition, message):
    if not condition:
        raise CaseFailure(message)


def run_case(case):
    """Build a fresh, isolated set of temp dirs, drive one real session
    against them, and assert only the case's declared consequences.

    Never touches the operator's real ~/.claude/skills or
    ~/.claude/growth-loop: GROWTH_LOOP_HOME and GROWTH_LOOP_SKILL_ROOTS are
    always pointed at directories created here, and every one of them is
    passed to --add-dir so the session can actually reach it.
    """
    home = Path(tempfile.mkdtemp(prefix="growth-loop-e2e-home-"))
    skills_root = Path(tempfile.mkdtemp(prefix="growth-loop-e2e-skills-"))
    workdir = Path(tempfile.mkdtemp(prefix="growth-loop-e2e-work-"))
    stdout = ""
    try:
        plant_skills(skills_root, case.get("plant_skills"))
        before = skill_dir_names(skills_root)

        proc = invoke_claude(case, home, skills_root, workdir)
        stdout = proc.stdout

        after = skill_dir_names(skills_root)
        new_dirs = after - before
        expect = case.get("expect", {})

        if "exit_code" in expect:
            check(proc.returncode == expect["exit_code"],
                  "exit code was %d, expected %d\n--- stderr ---\n%s"
                  % (proc.returncode, expect["exit_code"], proc.stderr))

        if expect.get("no_new_skill_directory"):
            check(len(new_dirs) == 0,
                  "expected no new skill directory under the scratch skills "
                  "root, found: %s" % sorted(new_dirs))

        new_slug = None
        if expect.get("exactly_one_new_skill_directory"):
            check(len(new_dirs) == 1,
                  "expected exactly one new skill directory, found: %s"
                  % sorted(new_dirs))
            new_slug = next(iter(new_dirs))
            check((skills_root / new_slug / "SKILL.md").is_file(),
                  "new directory %s has no SKILL.md" % new_slug)

        if expect.get("journey_lists_new_skill"):
            check(new_slug is not None,
                  "journey_lists_new_skill requires "
                  "exactly_one_new_skill_directory to have matched first")
            returncode, location = locate_skill(skills_root, home, new_slug)
            check(returncode == 0,
                  "gl-journey --locate %r did not find the skill learn just "
                  "wrote (exit %d) - learn and journey disagree on where "
                  "skills live\n--- gl-journey --locate output ---\n%s"
                  % (new_slug, returncode, location))
            located = Path(location.strip())
            expected_dir = skills_root / new_slug
            check(located.resolve() == expected_dir.resolve(),
                  "gl-journey --locate %r resolved to %s, not the directory "
                  "learn just wrote (%s)" % (new_slug, located, expected_dir))

        for template in expect.get("files_present", []):
            path = Path(resolve(template, home, skills_root))
            check(path.exists(), "expected to exist: %s" % path)

        for template in expect.get("files_absent", []):
            path = Path(resolve(template, home, skills_root))
            check(not path.exists(), "expected to be absent: %s" % path)

        for needle in expect.get("stdout_contains", []):
            check(needle in stdout,
                  "expected stdout to contain %r\n--- stdout ---\n%s"
                  % (needle, stdout))

        for needle in expect.get("stdout_absent", []):
            check(needle not in stdout,
                  "expected stdout NOT to contain %r\n--- stdout ---\n%s"
                  % (needle, stdout))

        profile_path = home / "profile.md"
        profile_text = (profile_path.read_text(encoding="utf-8")
                        if profile_path.is_file() else "")

        for needle in expect.get("profile_contains", []):
            check(needle in profile_text,
                  "expected profile.md to contain %r\n--- profile.md ---\n%s"
                  % (needle, profile_text))

        for needle in expect.get("profile_absent", []):
            check(needle not in profile_text,
                  "expected profile.md NOT to contain %r\n"
                  "--- profile.md ---\n%s" % (needle, profile_text))

        return True, None, stdout
    except subprocess.TimeoutExpired:
        return False, "claude did not finish within %ds" % TIMEOUT_SECONDS, stdout
    except CaseFailure as exc:
        return False, str(exc), stdout
    finally:
        shutil.rmtree(home, ignore_errors=True)
        shutil.rmtree(skills_root, ignore_errors=True)
        shutil.rmtree(workdir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", help="run only the case with this name")
    args = parser.parse_args()

    if os.environ.get("GROWTH_LOOP_E2E") != "1":
        print(
            "SKIPPED: this harness drives real Claude Code sessions against "
            "the real skills. Each case costs roughly 1-5 minutes and real "
            "subscription quota, so it does not run by default and "
            "`unittest discover` never touches it. To run it:\n\n"
            "    GROWTH_LOOP_E2E=1 python3 e2e/run_e2e.py\n"
        )
        return 0

    if shutil.which("claude") is None:
        print("SKIPPED: no `claude` executable on PATH; cannot drive a "
              "real session.")
        return 0

    cases = load_cases(args.case)
    if not cases:
        print("no case named %r under %s" % (args.case, CASES_DIR))
        return 1

    passed, failed = 0, []
    for case in cases:
        name = case["name"]
        print("=== %s ===" % name)
        ok, message, _stdout = run_case(case)
        if ok:
            print("PASS: %s" % name)
            passed += 1
        else:
            print("FAIL: %s" % name)
            print(message)
            failed.append(name)
        print()

    print("%d/%d passed" % (passed, len(cases)))
    if failed:
        print("failed: %s" % ", ".join(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
