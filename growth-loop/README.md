# growth-loop

A Claude Code plugin that closes a learning loop around your sessions: work
finishes, knowledge gets captured as a skill or a profile entry, that capture
gets reviewed on a schedule you control, and anything stale gets deleted
instead of quietly accumulating. Nothing here talks to a network, reads a
credential, or runs unattended — it exists entirely inside interactive Claude
Code sessions.

## What it adds

Six commands cover the five stages of the loop — distil, correct, recall,
model, review — plus deletion as its own explicit step. Four are things
Claude reaches for on your behalf during ordinary work; two are yours alone,
because review and deletion are decisions a human makes, not defaults a model
should reach for mid-task.

| Command | Invoked by | Does |
|---|---|---|
| `/growth-loop:learn [target]` | Claude or you | Distils a skill from work that just finished |
| `/growth-loop:refine` | Claude or you | Corrects a skill the moment it proves wrong |
| `/growth-loop:recall [query]` | Claude or you | Recovers reasoning from past sessions |
| `/growth-loop:profile` | Claude or you | Maintains the cross-project model of you |
| `/growth-loop:journey` | **you only** | Monthly review with forced verdicts |
| `/growth-loop:forget [target]` | **you only** | Deletes completely, after confirmation |

`journey` and `forget` carry `disable-model-invocation: true` — Claude cannot
trigger a deletion or a review on its own. Everything a model can silently
add, only a human can silently remove.

## Non-goals

Most rows below are capabilities Claude Code (or the wider Claude ecosystem)
already ships. growth-loop does not reimplement any of them. Duplicating a
built-in produces two half-working systems — one inside this plugin that
nobody maintains to the same standard, and one in the platform that already
gets it right — so the scope stops at the edge of what the harness does not
already do. One row is out for a different reason, noted where it applies:
not because something covers it, but because this plugin excludes it by
requirement.

| Out | Covered by |
|---|---|
| Cron / scheduling | `/loop` (recurring prompts) and scheduled cloud agents / routines, which already run work on a cron-like schedule |
| Subagent orchestration | Claude Code's own subagent dispatch (the Task tool) and multi-agent workflow features |
| Chat surfaces | Claude's own chat integrations (e.g. Claude Tag / Claude in Slack) |
| Terminal backends | Claude Code's own CLI, its VS Code and JetBrains extensions, and the Desktop app |
| MCP | Claude Code's native MCP client (`claude mcp add` / `remove` / `list`) |
| Compress / undo / retry | `/compact`, `/rewind`, and the harness's own resumable execution for subagents and workflows |
| Image / video / TTS | — (excluded by requirement) |

That last row is a scope decision, not a coverage claim: no built-in is being
credited for it. Image, video, and TTS generation have nothing to do with a
learning loop over skills and memory, so they were excluded from this plugin
by requirement from the start, independent of whether anything else already
covers them.

If a future built-in turns out to cover part of what remains here, the right
move is to shrink this plugin, not to keep both.

## Install

```bash
git clone <repo> growth-loop
cd growth-loop/growth-loop
chmod +x bin/*                    # required — the Stop hook depends on it
claude --plugin-dir .
```

The repo nests the plugin one level down — this checkout's own `bin/` lives
at `growth-loop/bin/` relative to the repo root, not at the root itself — so
`cd` into the inner `growth-loop/` before touching `chmod` or pointing
`--plugin-dir` anywhere.

`chmod +x` is not boilerplate. The `Stop` hook invokes
`"${CLAUDE_PLUGIN_ROOT}"/bin/gl-nudge` directly by path; without the
executable bit it still fails to launch and the nudge silently never fires
— there is no error, just a plugin that appears installed and does
nothing.

Note: `claude plugin init growth-loop` is not an alternative install path
for this plugin. It scaffolds a *new, empty* plugin skeleton at
`~/.claude/skills/growth-loop/`, which would collide by name with the one
above — it exists for authoring a plugin from scratch, not for installing
this one. If you edit plugin files while a session is already running, run
`/reload-plugins` to pick up the change without restarting.

## Verify

```bash
claude plugin validate .               # manifest + frontmatter + hooks schema
./bin/gl-recall --list-roots           # must print at least one root
./bin/gl-journey                       # inventory
./bin/gl-journey --paths               # the write targets learn and profile resolve
```

Run all four from the same directory the install block left you in — the
inner `growth-loop/growth-loop/`, where `.claude-plugin/` and `bin/`
actually live.

To syntax-check the scripts, do it without writing bytecode:

```bash
python3 -c 'import ast,sys; [ast.parse(open(f).read()) for f in sys.argv[1:]]' bin/*
```

`python3 -m py_compile bin/*` works too, but it leaves a `__pycache__`
directory beside the scripts — three extra files inside a plugin that is
supposed to contain exactly thirteen.

**`bin/` is not added to the Bash tool's `PATH`.** That was the plan going
in, but measuring it in a live session showed otherwise: with only this
plugin's manifest and `bin/` on disk, `gl-recall`, `gl-nudge`, and
`gl-journey` all come back `command not found` (exit 127) when invoked bare,
and `which` finds none of them. This reproduces with a minimal throwaway
plugin containing nothing but a manifest and one `bin/` script, so it is
general `--plugin-dir` behaviour, not specific to this plugin.

Because of that, every skill in this plugin invokes its script by explicit
path — `"${CLAUDE_PLUGIN_ROOT}"/bin/gl-recall`, `"${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey`
— which does substitute correctly inside a skill's markdown body and inside
its `allowed-tools` frontmatter. If you are running one of these scripts by
hand from a plain shell rather than through a skill, `$CLAUDE_PLUGIN_ROOT`
is not set for you either, so use the path under wherever you installed the
plugin, e.g. `~/.claude/plugins/.../growth-loop/bin/gl-recall`, or `./bin/gl-recall`
from inside this directory as shown above.

Inside a session, `/hooks` should show `gl-nudge` registered on both `Stop`
and `SessionEnd`. If `--list-roots` finds nothing, set
`CLAUDE_TRANSCRIPT_DIR` to the directory holding your `.jsonl` session files
— transcript storage locations drift between platforms and versions, and
autodiscovery only covers the well-known ones.

## Layout

```
growth-loop/
├── .claude-plugin/plugin.json      manifest — name, version, description, author
├── README.md                       this file
├── skills/
│   ├── learn/SKILL.md              distil a skill from finished work
│   ├── refine/SKILL.md             correct a skill the moment it proves wrong
│   ├── recall/SKILL.md             recover context from past sessions
│   ├── profile/SKILL.md            maintain the cross-project model of you
│   ├── journey/SKILL.md            monthly review, user-invoked only
│   └── forget/SKILL.md             deletion, user-invoked only
├── agents/skill-author.md          subagent that writes SKILL.md documents and nothing else
├── hooks/hooks.json                registers gl-nudge on Stop and SessionEnd
└── bin/
    ├── gl-recall                   deterministic transcript search
    ├── gl-nudge                    session-weight heuristic + cooldown + ledger
    └── gl-journey                  asset inventory with staleness
```

State lives outside the plugin, in `~/.claude/growth-loop/` — `profile.md`,
`ledger.jsonl`, `nudge-state.json` — overridable with `GROWTH_LOOP_HOME`.
Distilled skills are written to `~/.claude/skills/<slug>/SKILL.md`, not
inside this plugin, so they load globally across every project and survive
this plugin being removed.

`gl-journey --paths` prints the two write targets it has resolved:

```
skills-root: /Users/you/.claude/skills
profile: /Users/you/.claude/growth-loop/profile.md
```

`learn` and `profile` run that before writing, rather than assuming a path.
Resolution therefore happens once, in the same code that decides where the
sweep reads, so a distilled skill can never land somewhere the review will
not look.

`gl-journey` scans `~/.claude/skills` and `./.claude/skills` for `SKILL.md`
files by default — exactly where the learning loop writes and nowhere else,
so a review never surfaces someone else's installed plugins alongside your
own distilled skills. Override the sweep with `GROWTH_LOOP_SKILL_ROOTS`, an
`os.pathsep`-separated list of roots, if you deliberately want a wider scan.

## Tuning

| Constant | File | Default | Meaning |
|---|---|---|---|
| `MIN_TOOL_CALLS` | `bin/gl-nudge` | 25 | Minimum tool calls before the nudge fires |
| `MIN_EDITS` | `bin/gl-nudge` | 3 | Minimum mutating calls — reading is not doing |
| `COOLDOWN_SECONDS` | `bin/gl-nudge` | 21600 | At most one nudge per 6h, shared by both events |
| `STALE_DAYS` | `bin/gl-journey` | 90 | Age at which an asset needs a verdict |
| `SNIPPET_CHARS` | `bin/gl-recall` | 400 | Window around each transcript match |

These defaults are deliberately conservative. **The failure mode of this
whole plugin is a nudge you learn to ignore** — once that happens, lowering
the thresholds back down does not restore your attention to it. Loosen these
only after you notice yourself wishing the nudge had fired and it did not.
Do not tighten them preemptively; tightening after habituation has already
set in does not undo the habituation.

## Design notes

- **Skills are built from execution, not written in the abstract** (Voyager)
  — `learn` only fires on work that already happened, never on a plan for
  work that might.
- **Negative knowledge is the moat.** Any model can reconstruct the happy
  path from first principles; what it cannot reconstruct is which plausible
  approach silently failed. That is why *What goes wrong* is a mandatory
  section, not an optional one, in every skill this loop produces.
- **Correct at failure time, not in retrospect** (Reflexion) — `refine` fires
  the moment a skill proves wrong during a session, while the failure is
  fully understood, instead of waiting for a review pass to rediscover it.
- **Memory needs curation, not accumulation** (Generative Agents, MemGPT) —
  `journey` and `forget` are first-class, not afterthoughts, and deletion in
  `forget` means deletion: no tombstones, no `[deprecated]` markers, nothing
  that keeps loading every session while returning nothing.
- **Progressive disclosure.** Transcript search happens in `bin/gl-recall`,
  outside the model, so the model spends context on the answer rather than
  the search.
- **The person travels between repos; the project does not.** `profile.md`
  sits in `~/.claude/growth-loop/`, outside any repository, for exactly that
  reason — a fact recorded in one repo's `CLAUDE.md` is invisible from the
  next repo the same person opens tomorrow.

## Hook delivery

`gl-nudge` is registered on both `Stop` and `SessionEnd`, and the two events
deliver its output to two different audiences — this is the single most
surprising thing about the implementation, verified against the live hooks
reference on 2026-08-04:

- **On `Stop`**, exiting 0 with JSON whose `hookSpecificOutput.additionalContext`
  field is set reaches **Claude**, as a system reminder injected before the
  next model call. This is the mechanism `gl-nudge` relies on to prompt
  Claude toward `/growth-loop:learn` or `/growth-loop:profile` mid-session.
- **On `SessionEnd`**, there is no next model call for a reminder to precede
  — the session is ending — and hook stdout does not reach Claude at all.
  So on `SessionEnd`, `gl-nudge` instead emits a `systemMessage`, which is
  shown directly to **you**, the human, as the session closes.

In both cases `gl-nudge` exits 0. It never uses exit 2 and never sets
`decision: "block"` on `Stop`: either would force the agent to keep going
against its own judgment and would burn the harness's consecutive-block cap.
An advisory nudge that can force continuation is not advisory, so the hook
does not do that on any path — including every internal failure path, which
also exits 0 silently rather than surfacing an error into your session.

## Usage limits and compliance

Everything in this plugin runs inside the official Claude Code harness. No
OAuth token is read, extracted, proxied, or passed anywhere, because routing
subscription credentials through third-party tools is prohibited. Advertised
Pro and Max usage limits assume
ordinary, individual use of Claude Code and the Agent SDK; nothing here
encourages or enables unattended, always-on operation. The nudge fires at
most once per six hours and only inside a session you are actively running —
this plugin is built for interactive use, not for a process left running
against a limit. `bin/` is Python 3 standard library only: no `pip` installs,
no network calls, no telemetry, of any kind.
