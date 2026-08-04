---
name: journey
description: Reviews everything the learning loop has accumulated - skills, memory files, the nudge ledger - and forces a verdict on each stale item. Run this deliberately, about monthly, or when the skill library has grown past the point where you can name what is in it. Review is a human decision, so this skill is never invoked automatically.
disable-model-invocation: true
---

## Gather

Run `gl-journey`, then run `gl-journey --stale 60`. The first pass is the
full inventory — every skill, the memory files, the nudge ledger. The
second narrows to what is actually due: items older than 60 days, well
short of the 90-day staleness flag, so the review catches things before
they have sat unexamined for a full quarter.

Read both before deciding anything. The full inventory tells you what
exists; the narrowed one tells you what needs a decision today.

## The verdict

Every item `gl-journey --stale 60` surfaces gets exactly one of three
verdicts. No undecided leftovers.

- **Delete** — it no longer applies, or should never have been written.
  Route it to `/growth-loop:forget`.
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

## Audit the description set

Read every skill's description together, as a set, not one at a time. A
description that looks fine in isolation can still overlap the neighbor it
is never read next to. The question for each pairing: given a task,
would exactly the right one fire? Two descriptions that both plausibly
match the same task mean the wrong one sometimes wins; a description vague
enough to match nothing in particular means none of them fire and the task
gets redone from scratch instead of recalled.

## Report

Give a short verdict, not the inventory. The user already ran `gl-journey`
and can see the raw listing themselves; what this review owes them is the
decisions it produced — what got deleted, what got corrected, what got
kept and why, and any duplicates merged. Restating the table `gl-journey`
already printed tells them nothing they did not have before running this
skill.
