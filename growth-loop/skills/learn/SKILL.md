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

Resolve the directory before writing. Do not assume a path:

```bash
"${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey --paths
```

Take the `skills-root:` line and write to `<that directory>/<slug>/SKILL.md`,
where `<slug>` is the skill name in kebab-case.

That command reports the first place `gl-journey` itself looks, so a skill
written there is a skill the overlap check above will find next time.
Writing to a hardcoded `~/.claude/skills` instead breaks that check the
moment anyone redirects the roots — `learn` would keep writing where
`gl-journey` no longer reads, and every new skill would look like the first
of its kind. Do not try to resolve the path with a shell expansion such as
`${GROWTH_LOOP_SKILL_ROOTS:-...}` either: some hook policies refuse any
command containing an expansion, and the skill then falls back to guessing.

The directory sits outside the plugin on purpose, so a distilled skill
survives `growth-loop` itself being removed.

**Check the target does not already exist before writing.** If
`<slug>/SKILL.md` is already there, stop. Do not overwrite it and do not
quietly pick `<slug>-2`. Writing over a skill destroys it exactly as much
as deleting it would, and this is the one place in the loop where a
model-invoked skill could do that without anyone being shown what was lost
— `forget` requires showing the content and waiting for confirmation, so
this path must not become the way around that.

Two things reach this point. Either the existing skill covers the same
ground, which the overlap check above should have caught, and the answer is
`/growth-loop:refine`. Or the slug collides on unrelated content, and the
answer is a different slug that names this skill's situation more
precisely — report the collision either way rather than resolving it
silently.

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

## Pending jots

`/growth-loop:jot` queues raw, ungated notes mid-session without running any
of the checks above. Those checks still have to happen somewhere, and this
is that somewhere.

Resolve the queue the same way you resolved the skills root:

```bash
"${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey --paths
```

Take the `candidates:` line. If that file has entries (each one a `## `
heading), read them along with whatever prompted this invocation.

For each entry, apply the exact same rules as above: the overlap check
against existing skills, then the three-condition gate. An entry that
passes both gets promoted through the same template and the same
existence check as any other distillation. An entry that fails either one
gets dropped from the queue without becoming a skill - a jot was never
gated at write time, so this is the first and only place that judgment
happens; leaving a rejected entry sitting in the file just means re-reading
and re-rejecting it next time.

Either way - promoted or dropped - remove that entry from `candidates.md`
once you have decided. Edit the file to delete only that entry's block;
leave every other pending entry untouched. A queue that only ever grows is
the same failure mode `learn` itself exists to prevent, one level up.

## Delegating

If the session has been long, dispatch the `skill-author` subagent to write
the document rather than writing it inline — this keeps the distillation
work out of the main session's context. Hand it the facts directly: what
was attempted, what failed and why, and what finally worked. It writes the
document; you do not need to draft it first.

**Do the two checks above yourself and hand over their results**, because
the subagent cannot repeat them: it has no `${CLAUDE_PLUGIN_ROOT}` to
resolve, so it cannot run `gl-journey --paths` and cannot see whether the
target already exists. Give it the resolved absolute path to write, and
confirm that path is free before dispatching. Delegation is triggered by a
long session — exactly when the resolved path is least likely to still be
in view — so leaving either check to the subagent is how the delegated
branch ends up writing to a hardcoded root, or over a skill that was
already there.

## Reporting

Afterwards, report only two things: the path the skill was written to, and
its description line. Do not paste the skill's body back into the
conversation — the reader can open the file if they want it.

## Handling $ARGUMENTS

- `$ARGUMENTS` empty: distil this conversation, then process pending jots
  (see above).
- `$ARGUMENTS` a directory: read it and distil the procedure it encodes.
- `$ARGUMENTS` a URL: fetch it and distil the procedure it describes.

The same gate applies to all three — a directory or URL that fails the gate
gets nothing written, exactly as an empty-argument call would.
