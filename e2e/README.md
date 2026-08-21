# e2e — behavioural harness

`e2e/` drives the real seven skills in real Claude Code sessions and checks
what actually happened, not what the prose says should happen. It is
separate from `tests/` (the unit suite over the skill files themselves) and
separate from the plugin (`growth-loop/`, which must stay at exactly 14
files). `e2e/` ships in neither.

## Why this exists

The unit suite asserts that particular sentences exist in the skills' prose.
In seven rounds of defect-fixing on this plugin, that suite never once found
a defect ahead of a review or a live run — it only pinned defects that had
already been found by other means. Every defect that actually mattered came
from running the thing:

- `bin/` is not on the Bash tool's `PATH`, so a skill's first command failed.
- `learn` wrote where `journey` did not read, silently breaking the overlap
  check the whole loop depends on.
- `refine` refused a route `journey` documented, because their evidence
  contracts disagreed.
- A confirmation gate had to be checked with `Bash`, `Write`, and `Edit` all
  granted — a gate that only holds because permission was withheld proves
  nothing.

None of these show up as a missing sentence. They show up as: a command that
was never reached, a file in the wrong place, a directory that should not
have been touched.

## Why it is opt-in

Each case is a real `claude -p` call against a real model. That is minutes
of wall-clock time and real subscription quota per case, run sequentially
(parallel cases would just race each other into rate limits). `tests/run.py`
has to stay fast enough to run on every edit, so this harness never runs as
part of it — it refuses outright unless `GROWTH_LOOP_E2E=1`, and
`unittest discover` (used by `tests/run.py`) never looks outside `tests/`,
so adding `e2e/` does not change the default suite's count or its ~2 second
runtime.

```bash
GROWTH_LOOP_E2E=1 python3 e2e/run_e2e.py            # all cases
GROWTH_LOOP_E2E=1 python3 e2e/run_e2e.py --case NAME  # one case
```

Without `GROWTH_LOOP_E2E=1` it prints why it is skipping and exits 0.

## Why it asserts consequences, never prose

Model output is nondeterministic — the same prompt produces different
wording on every run. A test that compares transcript text to a fixed
string is a coin flip dressed as a regression test: it fails on wording
that has nothing to do with a defect, and a flaky test gets disabled, which
is worse than no test.

What does not vary between runs of the same case is the **observable
consequence**: which files exist afterwards, whether a directory was
created or left alone, whether a script another skill depends on can
actually see what got written, and the process exit code. Every defect in
the list above turns on one of those. So each case's `expect` block is
built only from:

- `no_new_skill_directory` — nothing new appeared under the scratch skills
  root.
- `exactly_one_new_skill_directory` — exactly one new `<slug>/SKILL.md`
  appeared (and the harness records the slug for the next check).
- `journey_lists_new_skill` — the real `gl-journey --locate <slug>`,
  invoked directly (no model call — it is a deterministic script, and
  calling it straight is faster and more reliable than asking a second
  model session to describe what it sees), resolves to the directory
  `learn` just wrote. This is the exact check that would have caught the
  "`learn` writes where `journey` does not read" defect. It uses
  `--locate`, not the plain listing: the plain listing clips the name
  column at 28 characters to stay readable as a table, and the harness's
  first real run tripped over exactly that — a 29-character slug the model
  chose came back clipped to `ci-cert-error-stale-ca-bu...`, and a
  substring check against the clipped table reported a false failure even
  though `learn` and `journey` agreed perfectly on where the skill lived.
  That was a defect in the assertion, not in the plugin, and it is the
  concrete argument for the rule two paragraphs up: check a machine-facing
  command's exit status and its exact output, never grep formatted,
  column-width-limited, human-facing text.
- `files_present` / `files_absent` — a path exists or does not, after
  `{home}` / `{skills_root}` are substituted for the case's scratch
  directories.
- `stdout_contains` / `stdout_absent` — a literal, structural token appears
  or does not: a slash-command route name (`/growth-loop:refine`), a slug
  the model had to name to prove it engaged with the actual target rather
  than declining everything by accident. Never a sentence, never a style of
  phrasing.
- `profile_contains` / `profile_absent` — the same idea, applied to the
  content of `profile.md` instead of stdout.

Keep this vocabulary small. Every additional predicate is one more way for
the harness to fail on wording instead of on a defect.

## What never gets touched

Every case builds three fresh temp directories — one for `GROWTH_LOOP_HOME`,
one for `GROWTH_LOOP_SKILL_ROOTS`, one as the session's working directory —
and passes all three to `--add-dir` so the session can actually reach them.
The operator's real `~/.claude/skills` and `~/.claude/growth-loop` are never
in that list, which matters twice over: the scripts never read or write
there because the env vars point elsewhere, and a session can only read or
write inside directories it was explicitly given, so even a skill that
regressed back to a hardcoded path would hit a permission wall before it
could touch real state. Temp directories are removed after each case,
pass or fail.

## The four cases

Each corresponds to a defect class that a live run actually caught in
v0.1.0 (see `docs/superpowers/CURRENT.md` for the incident write-ups):

| Case | Defect class it targets |
|---|---|
| `learn-declines-a-duplicate` | `learn` writing a second skill instead of routing an overlap to `refine` |
| `forget-holds-without-confirmation` | a confirmation gate that only holds because permission was withheld |
| `learn-writes-where-journey-reads` | `learn` and `journey` disagreeing about where skills live |
| `profile-refuses-dishonesty` | a skill persisting an instruction that would make future sessions less honest |

## Adding a case

Drop a new `e2e/cases/<name>.json`:

```json
{
  "name": "some-case-name",
  "prompt": "/growth-loop:<skill>\n\n...material that exercises the defect...",
  "plant_skills": [{"slug": "...", "description": "...", "body": "..."}],
  "permission_mode": "acceptEdits",
  "allowed_tools": ["Bash", "Read", "Write", "Edit"],
  "expect": {
    "no_new_skill_directory": true,
    "stdout_contains": ["/growth-loop:refine"]
  }
}
```

`plant_skills` and `allowed_tools` are optional. `permission_mode` defaults
to `acceptEdits` if omitted. `run_e2e.py` picks up every `*.json` file under
`e2e/cases/` automatically — no registration step.

Before writing the case, ask the question this file keeps repeating: what
defect does this assertion catch, and could the case still pass while that
defect is present? If the answer is "yes, if the model does nothing at
all" or "yes, if it just says a certain word," the assertion is not testing
anything yet.
