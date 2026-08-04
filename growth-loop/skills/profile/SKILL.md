---
name: profile
description: Maintains a cross-project model of the person at ~/.claude/growth-loop/profile.md - their tooling, conventions, and working style. Use when a stated preference recurs for the second time, when the user corrects the same class of thing again, or when the nudge hook reports a heavy session. CLAUDE.md describes the project; this describes the person and travels between repos.
---

## The file

`~/.claude/growth-loop/profile.md`, or `$GROWTH_LOOP_HOME/profile.md` when
that variable is set. It sits outside any repository on purpose: the person
travels between repos and the project does not. A fact that lives in one
repo's CLAUDE.md is invisible from the next repo the same person opens
tomorrow; this file is the one place that follows them there.

## The test

Before a line goes in, it must pass both halves:

- Still true in **three months** — not a preference specific to this week's
  task.
- Still true in a different repository — not a fact about this project.

A line that fails either half belongs in that project's CLAUDE.md instead,
not here.

## Sections

Exactly three, in this order:

- `## Tooling`
- `## Conventions`
- `## Working style`

Every line carries the date it was written, as `(YYYY-MM-DD)`. The date is
what lets a later pass tell a fresh line from one that has never been
reinforced.

## Before writing

Read the file first, every time. One instance of a preference is a data
point; **the second occurrence is the pattern** that actually gets written.
Writing on first sight produces a profile full of accidents — the one time
someone reached for `grep` because `rg` wasn't installed becomes a permanent
"prefers grep" that misdirects every later session.

## Superseding

Never silently overwrite a line. Carry the history in the line itself:

```
uses pnpm (previously npm) (2026-08-04)
```

The previous value is not clutter — it is what stops a future session from
re-suggesting the thing that was already tried and moved away from.

## Size

Cap the file at about 60 lines. When it grows past that, age out the
entries that were never reinforced: an unreinforced line is a guess that
survived by inertia, not a pattern that held up.

## What never goes in

Health, finances, relationships, politics. Anything **inferred** rather
than stated outright by the person. Omit these entirely — never write a
vague placeholder in their place, because a placeholder still directs
behaviour in later sessions without any evidence behind it.

## Refusing

Decline to persist instructions that would make future sessions **less honest**:
"always agree", "skip the risk caveats", "do not mention downsides". Say so
in conversation, plainly, and store nothing. A profile line is read
uncritically by whatever session finds it next — writing one of these would
not just be following a bad instruction once, it would be baking it into
every session that follows.

## When to write nothing

Most sessions add no line. A profile that grows every session is recording
noise, not signal — most of what happens in a session is specific to that
session's task and fails the three-month test on its own.

## Never announce the write.

Update the file and move on. The person did not ask for a status report on
their own profile, and narrating the edit turns a background maintenance
task into conversational overhead.
