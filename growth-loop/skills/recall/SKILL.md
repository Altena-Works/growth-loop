---
name: recall
description: Recovers context from past Claude Code sessions by searching transcripts. Use when the user refers to earlier work without restating it - "how did we fix that", "what was the workaround", "we decided something about this" - or when a task resumes and the reasoning behind the current state is not in context. Searches deterministically outside the model, then summarises.
argument-hint: "[what to search for]"
---

## Search

Run `gl-recall "<query>"`. Start with the user's own words — the phrase they
just used is the one most likely to appear in the transcript that recorded
it. If the memory is old, widen the window with `--days 365`; the default
window is shorter and will miss it.

If the first pass comes back thin, widen the query with the concrete strings
that would actually appear in a transcript — error text, filenames, command
names — not paraphrases of them. A paraphrase is your words, not the
session's; `gl-recall` matches what was typed, not what was meant.

## Reading the hits

Read **newest session first** — `gl-recall` already orders results that
way, and a later session usually supersedes an earlier one on the same
question.

Within a session, prefer the **resolution** over the discussion around it.
What was **decided** outranks what was merely considered, and a transcript
contains far more of the latter than the former: most of the text is the
back-and-forth that led somewhere, not the somewhere. Watch specifically for
the pattern where an approach is discussed at length and then abandoned in
one line — that one line is the answer, and it is easy to skim past because
it is short next to the paragraphs that came before it.

## Answering

Answer the user's actual question, **conclusion first**, then the
supporting detail they can ask for if they want it. Never dump raw
`gl-recall` output into the conversation — that spends the exact context
this tool exists to protect, and it hands the user your homework instead of
your answer.

## When nothing is found

Before reporting a dead end, run `gl-recall --list-roots`. If it reports no
root, the search never actually ran — say so, and give the remedy: set
`CLAUDE_TRANSCRIPT_DIR` to the directory holding the `.jsonl` session files,
then search again. Do not report "no history" when the real problem is that
no history was searched.

## Close the loop

A fact that had to be **searched twice** should not need a third search.
Recall is the fallback for context that was never written down; persistence
is the fix that makes the next search unnecessary. Route facts about this
project to CLAUDE.md, and facts about the person doing the work to
`/growth-loop:profile`.
