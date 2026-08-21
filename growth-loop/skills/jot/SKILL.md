---
name: jot
description: Captures a one-line note the instant something in the conversation looks worth remembering later, without the overhead of a full skill. Use when a plausible dead end, a non-obvious flag, or a hard-won detail surfaces mid-task and stopping to run the full /growth-loop:learn gate would break flow; also use when the user says "note that down" or "jot this". Not a substitute for learn - it queues raw material that learn's overlap check and three-condition gate still judge before anything becomes a skill.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey:*)
---

## The one condition

Write a jot only when reconstructing this later would cost real time - not
every detail worth mentioning in chat is worth queuing. If it fails that,
say nothing and keep working; jot is not a running commentary on the
session.

This is the only gate here. The three-condition check `learn` applies (real
work, will recur, procedural) and the overlap check against existing skills
both happen later, at promotion time - not now, and not by this skill.

## Where it goes

Resolve the file before writing:

```bash
"${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey --paths
```

Take the `candidates:` line and append to it. Never overwrite the file and
never choose a different path - the file does not need to exist yet;
appending creates it.

## What to write

Append exactly one entry, in this shape:

```markdown
## <date> — <one-line title>
project: <cwd>
<2-5 sentences: what was attempted, what failed, what worked>
```

This is raw material, not a finished skill: no "When this applies" / "The
approach" / "What goes wrong" headings. `/growth-loop:learn` reads pending
entries here and applies its own gate and template when it promotes one -
that is the only place a jot becomes a real `SKILL.md`.

## Reporting

One sentence after writing: the entry's title, and that it is recorded. Do
not read the note back in full and do not ask for confirmation before
writing it - the point of jot is that it does not interrupt the
conversation it is capturing from.
