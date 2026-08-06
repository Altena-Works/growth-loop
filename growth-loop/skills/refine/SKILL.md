---
name: refine
description: Corrects a stored skill against evidence in front of you - a step that failed, an assumption that no longer holds, a better route found, a description that fired at the wrong time, or a duplicate whose content has to be folded into the skill that supersedes it. Use when following a skill produced an error, when a documented command no longer exists, when the right skill did not fire for an obviously matching task, or when a review puts two overlapping skills side by side. Correct on evidence, never on a hunch.
---

## When this fires

- A step in a skill produced an error when followed.
- A documented command no longer exists, or its flags changed.
- A better route was found while following the skill's documented one.
- The right skill did not fire for a task it obviously matched, or a wrong
  one fired instead.
- A review found two descriptions that both plausibly claim the same task,
  so whichever fires first wins regardless of which is right — the files
  are in front of you, which is the same standard a merge meets.

Also, when a review puts two skills side by side and one has to absorb
what the other documents. That is a correction with both files in view, so
it belongs here rather than being done by hand — `/growth-loop:journey`
routes merges this way.

The hard rule: **refine on evidence in front of you, never on a hunch.**
Usually that means something that happened this session — the failing
command, its output, and the fix all still in view, which is when the
correction is worth writing and before the detail that mattered has faded.
A review that has both skills open is the same standard met a different
way. What is excluded is the same either way: a half-remembered past
failure, or a guess about what might be wrong.

## The procedure

Read the whole file first, before editing any of it. A targeted edit to a
file you have not read produces contradictions between sections: the step
you fix might already be referenced, hedged around, or contradicted three
sections down, and you will not see that until a future reader does.

Then make the smallest correct edit — replace the wrong step, wrong flag,
or wrong claim with the one that actually works, verified against the
evidence that brought you here: what just happened in this session, or the
other skill open beside this one.

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

If a review found two descriptions that both plausibly claim the same
task, the fix is the opposite shape: **narrow one of them** so it stops
claiming what the other owns, rather than broadening either. Decide which
skill genuinely owns the task, edit that one's neighbour, and put the
`## Revisions` entry in the file you edited — the one whose description
changed, not the one that kept its scope. Nothing fired wrongly yet, so
there is no situation to name; what you are recording is which of the two
now owns the overlap, and why.

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

`forget` carries `disable-model-invocation: true` — you cannot invoke it
yourself. Routing to it means presenting the skill and why it is beyond
repair, then stopping: let the person run `/growth-loop:forget` themselves.
Do not delete the directory yourself as a shortcut around that gate.

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

Missing is not the same as merely unhelpful. A keeper that lacks the dead
end its duplicate documents **is** wrong for the reader who follows it into
that dead end, so folding one in is a correction, not polish — this rule
does not decline a merge routed here by `/growth-loop:journey`.
