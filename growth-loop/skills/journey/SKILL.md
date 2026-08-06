---
name: journey
description: Reviews everything the learning loop has accumulated - skills, memory files, the nudge ledger - and forces a verdict on each stale item. Run this deliberately, about monthly, or when the skill library has grown past the point where you can name what is in it. Review is a human decision, so this skill is never invoked automatically.
disable-model-invocation: true
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey:*)
---

## Gather

Run `"${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey`, then run
`"${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey --stale 60`. The first pass is the
full inventory — every skill, the memory files, the nudge ledger. The
second narrows to what is actually due: items older than 60 days, well
short of the 90-day staleness flag, so the review catches things before
they have sat unexamined for a full quarter.

`--stale` narrows the SKILLS section only. MEMORY and LEDGER print in full
on both passes, so a memory file appearing in the second pass is not a
stale item — do not open a verdict on it for that reason alone.

Read both before deciding anything. The full inventory tells you what
exists; the narrowed one tells you what needs a decision today.

## The verdict

Every **skill** `gl-journey --stale 60` surfaces gets exactly one of three
verdicts. No undecided leftovers.

- **Delete** — it no longer applies, or should never have been written.
  Route it to `/growth-loop:forget`. `forget` carries
  `disable-model-invocation: true`, so this routing is a recommendation in
  the report, not an action you take: name what should go and why, then let
  the person invoke `/growth-loop:forget` themselves. Do not delete the
  directory yourself instead.
- **Verify and correct** — the knowledge underneath it might still hold but
  has not been checked in a while. Check it against reality now, then route
  the fix through `/growth-loop:refine`.
- **Keep and say so** — it is still correct despite its age. Say, in the
  report, why the age does not undermine it.

"I'll look at it later" is not one of the three. An item nobody can decide
on is an item nobody trusts, which is the same as deleted except the
context cost is still being paid every session it stays loaded.

## Duplicates

Hunt for skills covering the same ground under different names. The same
procedure described twice is worse than described once — whichever fires
first is the one followed, correct or not, and the reader has no way to
know a second version exists. When two overlap, merge into the one with
the better **What goes wrong** section, not the newer one: the dead ends it
documents are the irreplaceable part, and a newer skill that has not yet
failed at anything has nothing there to lose.

A merge has two halves and you perform only the first. Fold what the loser
has that the keeper lacks into the keeper — that is a correction, so route
it through `/growth-loop:refine`.
Then **recommend the loser for deletion and stop.** Do not delete it here.

Removing it yourself would destroy a skill that was never located, never
shown and never confirmed, in the middle of a review the user asked for —
the same thing `forget` exists to make impossible, reached from a section
that never mentions it. `forget` is user-invoked only and you cannot call
it; name the directory and let them.

Until they do, the merge is incomplete and the duplication is worse than
before, because the keeper now covers ground the loser still claims. Say
that plainly in the report rather than leaving it implied.

## Audit the description set

Read the descriptions **from the files**, not from the listing. The listing
clips each one at 90 characters, which cuts the "use when …" clause — and
that clause is the entire basis for the question below. Judging from the
clipped form is judging with the evidence removed. Open each `SKILL.md` and
read its frontmatter.

Read them together, as a set, not one at a time. A description that looks
fine in isolation can still overlap the neighbor it
is never read next to. The question for each pairing: given a task,
would exactly the right one fire? Two descriptions that both plausibly
match the same task mean the wrong one sometimes wins; a description vague
enough to match nothing in particular means none of them fire and the task
gets redone from scratch instead of recalled.

A description that mis-targets is `/growth-loop:refine`'s "fixing the
description" case — route it there and say so in the report, rather than
letting the audit end as an observation nobody acts on.

## Report

Give a short verdict, not the inventory. The user already ran `gl-journey`
and can see the raw listing themselves; what this review owes them is the
decisions it produced — what is recommended for deletion and why, what got
corrected, what got kept and why, and any duplicates folded together with
the loser named for deletion, and any descriptions routed to refine for
mis-targeting. Restating the table `gl-journey` already
printed tells them nothing they did not have before running this skill.
