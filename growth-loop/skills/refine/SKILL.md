---
name: refine
description: Corrects a stored skill the moment it proves wrong in use - a step that failed, an assumption that no longer holds, a better route found, or a description that fired at the wrong time. Use when following a skill produced an error, when a documented command no longer exists, or when the right skill did not fire for an obviously matching task. Correct at failure time, never as a retrospective.
---

## When this fires

- A step in a skill produced an error when followed.
- A documented command no longer exists, or its flags changed.
- A better route was found while following the skill's documented one.
- The right skill did not fire for a task it obviously matched, or a wrong
  one fired instead.

The hard rule: only on something that happened **this session**. Never
refine on a hunch, a half-remembered past failure, or a guess about what
might be wrong. The correction is worth writing exactly when the error is
fully understood, which is now — while the failing command, its output, and
the fix are all still in view — not later, when the detail that mattered
has already faded.

## The procedure

Read the whole file first, before editing any of it. A targeted edit to a
file you have not read produces contradictions between sections: the step
you fix might already be referenced, hedged around, or contradicted three
sections down, and you will not see that until a future reader does.

Then make the smallest correct edit — replace the wrong step, wrong flag,
or wrong claim with the one that actually works, verified against what just
happened in this session.

Then append a dated entry under `## Revisions` stating what changed **and
why**:

```markdown
## Revisions
- 2026-08-04: replaced `--force` with `--yes` — the flag was renamed
  upstream; `--force` now exits 2 with "unrecognized argument".
```

The why is what stops the next reader — human or model — from
re-introducing the old step because it looked reasonable in isolation.

## Fixing the description

If the failure was *targeting* — the skill did not fire when it should
have, or fired on a task it does not cover — the body is fine and the
description is the bug. Rewrite the description to name the exact situation
that just occurred, concretely enough that the same task would trigger it
next time.

## What not to do

Never soften a wrong step into a hedge. "This may not work on newer
versions" is not a correction — it is the original wrong step with a
disclaimer taped to it, and it costs the next reader the same failure the
disclaimer claims to warn about. Either state the condition precisely
("on v2 and later, use `--yes` instead of `--force`") or delete the step
outright.

## When it is beyond repair

If more than half the skill is wrong — built on an assumption that no
longer holds, or patched so many times that the throughline is gone — stop
editing and route to `/growth-loop:forget` instead.

**Beyond repair is a real verdict, not a failure to fix it well enough.** A
heavily patched skill built on a dead assumption still reads as
authoritative to whoever finds it next, and that is worse than no skill at
all — it costs them the time to find the failure themselves before they
can distrust it.

## When to write nothing

A skill that was merely unhelpful — vague, slower than it needed to be, not
quite matching this session's flavor of the task — but not actually wrong,
needs no edit. Do not churn a skill just because it could be phrased
better; refine corrects errors, it does not polish prose.
