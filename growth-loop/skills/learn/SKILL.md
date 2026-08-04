---
name: learn
description: Distils a reusable skill from work that just finished, when a task took real effort to get right and the same problem will come back. Use when the user says "remember how to do this", "write that down", or "make a skill for this"; when a multi-step procedure has just succeeded after several failed attempts; or when the nudge hook reports a heavy session. Takes an optional target - a directory or URL - and otherwise distils this conversation.
argument-hint: "[directory-or-url]"
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey:*)
---

## First: check for overlap

Before anything else, run `"${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey` and read
the SKILLS section. If an
existing skill already covers the same ground, stop here and route to
`/growth-loop:refine` instead of writing a second one.

Near-duplicates are the rot vector. Two skills describing the same procedure
differently means neither can be trusted: the next reader has to reconcile
them by hand, and the one that gets followed is whichever fires first, not
whichever is correct. One corrected skill beats two competing skills every
time.

## The gate

All three must hold, or nothing gets written:

- **It took real work.** The reader could not have reconstructed it from
  first principles — it took several failed attempts, a non-obvious flag, or
  a source that isn't the official docs.
- **It will recur.** The exact situation, or a close variant of it, will
  come up again in other sessions.
- **It is procedural.** It is a way of doing something, not a fact about one
  repository. A fact about this repo belongs in that repo's `CLAUDE.md`. A
  fact about the person — a tool they prefer, a convention they hold across
  projects — belongs in `/growth-loop:profile`, not here.

## When to write nothing

Most sessions do not deserve a skill. Saying "nothing here is worth keeping"
and stopping is a success, not a failure — a skill store that grows on every
session becomes noise the next reader has to wade through.

Common false positives to name and reject:

- A task that only felt hard because of an outage or a flaky dependency —
  the difficulty was circumstantial, not procedural, and will not recur.
- A one-off migration or cleanup that will never run again in this form.
- Anything already written down in the project's `CLAUDE.md` — restating it
  as a skill duplicates it under a name nobody will think to check.

## Where it goes

`~/.claude/skills/<slug>/SKILL.md`, where `<slug>` is the skill name in
kebab-case. This is deliberately outside the plugin directory, so the skill
survives `growth-loop` itself being removed.

## The template

```markdown
---
name: <slug>
description: <what it does + the exact situation that should trigger it>
---

## When this applies
## The approach
## What goes wrong
```

**The approach** carries verbatim commands with the flags that mattered.
"Run the migration" is useless to a future reader; `alembic upgrade head
--sql` is not.

**What goes wrong** is the payload. Any model can reconstruct a happy path
from first principles; what it cannot reconstruct is which plausible
approach silently failed and how that failure was recognised. Name the
route that looked right and wasn't, and the symptom that gave it away. A
distillation with no dead end is not worth writing — if you cannot name
one, go back to the gate: the task probably didn't take real work after
all.

## Delegating

If the session has been long, dispatch the `skill-author` subagent to write
the document rather than writing it inline — this keeps the distillation
work out of the main session's context. Hand it the facts directly: what
was attempted, what failed and why, and what finally worked. It writes the
document; you do not need to draft it first.

## Reporting

Afterwards, report only two things: the path the skill was written to, and
its description line. Do not paste the skill's body back into the
conversation — the reader can open the file if they want it.

## Handling $ARGUMENTS

- `$ARGUMENTS` empty: distil this conversation.
- `$ARGUMENTS` a directory: read it and distil the procedure it encodes.
- `$ARGUMENTS` a URL: fetch it and distil the procedure it describes.

The same gate applies to all three — a directory or URL that fails the gate
gets nothing written, exactly as an empty-argument call would.
