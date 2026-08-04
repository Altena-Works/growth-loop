---
name: forget
description: Deletes a skill or a profile entry completely, after showing exactly what will be removed and getting confirmation. Use when the user says "forget that", "delete that skill", or "that is no longer true". Deletion is a human decision, so this skill is never invoked automatically.
argument-hint: "[what to forget]"
disable-model-invocation: true
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey:*)
---

## Locate

Resolve `$ARGUMENTS` to one concrete target — a skill directory or a
specific profile line. If the reference is by topic rather than by name
("that skill about migrations" instead of "the migrations skill"), run
`"${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey` and match against its listing
instead of guessing from memory.

If the scope is ambiguous — several matches, or it is unclear whether the
user means a skill or a profile line — ask before touching anything. A
wrong guess here deletes the wrong thing, and there is no undo.

## Show

Before asking for confirmation, print exactly what will be removed, not a
summary of it: the full path for a skill directory, the literal line for a
profile entry. The person confirming needs to see the actual thing that is
about to disappear, not a paraphrase that could describe something else.

## Confirm

Wait for confirmation. Do not proceed on an implied yes — agreeing with the
description of the deletion is not the same as agreeing to the deletion
itself. Deletion is permanent; asking again is cheap by comparison.

## Delete

For a skill, delete the whole `<slug>/` directory, including any
supporting files inside it, not just `SKILL.md`. A partially deleted skill
with orphaned support files is worse than a whole one — it fails silently
instead of visibly.

For a profile entry, remove that line from the file and leave the rest of
the file untouched.

## Delete, do not soften

No `[deprecated]` markers, no "this may no longer apply", no commented-out
blocks. A tombstone is ambiguous context that still loads every single
session and still shapes behaviour; it costs what the original cost and
returns nothing — the reader still has to read it, and still has to guess
whether "may no longer apply" means never trust this or trust it most of
the time.

Genuine supersession is different from deletion: when a value changed but
the fact of the change is itself worth keeping, that is a
`/growth-loop:profile` update carrying the old value forward (`uses pnpm
(previously npm)`), not a comment left behind here. The word *forget* means
gone. If it should be gone, delete it outright; if it should be remembered
as history, that is profile's job, not this skill's.

## Follow the references

A deleted item rarely stands alone. Remove derived entries that depended on
it: profile lines that only made sense alongside the thing just deleted,
and other skills whose bodies point at it by name or route to it. A
reference to a skill that no longer exists is a dead end the next reader
has to discover the hard way, at the exact moment they are relying on it.
