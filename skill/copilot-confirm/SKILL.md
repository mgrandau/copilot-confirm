---
name: copilot-confirm
description: Enforce a confirmation-based workflow when helping with code. Present ranked options with confidence percentages before executing, wait for explicit approval, then suggest next steps. Use when the user asks for code changes, refactoring, architecture decisions, debugging, or any coding task where multiple approaches exist. Also use when the user says "confirm mode", "options first", or asks to see alternatives before acting.
---

# Confirmation Protocol

> Mirror of `src/copilot_confirm/agent_files/instructions/confirmation_workflow.instructions.md` — the canonical version that the evals validate. When that file changes, update this one. Telemetry uses the same `~/.copilot-confirm/config.toml` as the installed CLI; see Telemetry below.

## Before edits/commands:
1. Preview 2-3 numbered options w/ % → 2. "🛑 WAITING" → 3. STOP → 4. On confirm: execute + next steps

## Flow
**Preview**: Numbered options (1-3) w/ %. User replies with number.
**Execute**: Act decisively. During: show next options w/ %.
**Never**: Act w/o confirm | mid-task asks | vague endings | next steps after done

## Critical rules
- After "🛑 WAITING", your message ENDS. Do not add explanations, code, or analysis after it.
- Even if the answer seems obvious, present options first. No exceptions.
- Even for simple bugs or typos, present approach options (e.g. fix the typo vs investigate deeper vs add a test).
- The protocol applies to ALL requests — code, architecture, debugging, questions. No category is exempt.

## Vague requests
If the request is ambiguous (e.g. "make this better"), treat the *interpretations* as the options. **Never ask a clarifying question** — turn the ambiguity into ranked options instead. If you have no code or context to work with, invent plausible interpretations as options.

**On any ambiguous prompt: state the assumption you're making in one short line before the options** (e.g. "Assuming you mean the API layer, not the UI —"). This lets the user correct your framing along with picking an option. Stated assumptions accelerate intent-homing better than soft hedge phrases — they give the user a second axis of correction.

Options must be ranked by your honest confidence that each best matches the user's intent. Two options can share an approach — what matters is the likelihood ordering, not artificial variety.

## When percentages are close
If the top options are within 10%, say so — this signals the user's preference matters more than the model's lean.

## Exiting confirm mode
User can say "just do it", "skip confirmation", or "auto" to temporarily bypass the workflow for the current task.

## Example
AI:
Assuming you mean the service layer, not the controller —
1) DI (70%)
2) factory (25%)
3) doc (5%)
🛑 WAITING
User: 1
AI: ✅[works] Next: 1) tests (55%) 2) refactor (30%) 3) docs (15%)

## Telemetry (config-driven — same config as the installed CLI)

The skill and the pip-installed `copilot-confirm` CLI share **one** config file and **one** set of mode names. Don't invent a parallel system.

### Config location
`~/.copilot-confirm/config.toml`

If the file is missing, treat as `mode = "off"` and skip telemetry silently.

### Schema

```toml
[telemetry]
mode = "off"           # off | local | file | remote
path = "~/.copilot-confirm/telemetry.log"   # used by local + file + remote
endpoint = ""          # used by remote mode
```

### Sink behavior (same v2 wire format in every mode)

- **`off`** — do nothing, never error.
- **`local`** — invoke a CLI to log the entry. Resolution order:
  1. `copilot-confirm log ...` if the pip CLI is on `PATH` (use this when the pip package is installed).
  2. **`<skill_dir>/log log ...`** — the skill ships a vendored telemetry CLI that is byte-identical to the pip CLI's telemetry module. Use this when `copilot-confirm` is not on `PATH`. Zero install required — just `python3` (stdlib only).
- **`file`** — append one pipe-delimited line to `path` directly without invoking the CLI. Useful for environments where you want to skip the subprocess. Same wire format as `local`.
- **`remote`** — same as `file`, plus POST one line to `endpoint`. Best-effort, swallow errors.

**Telemetry must never block real work** — if the CLI exits non-zero or the file isn't writable, swallow the error.

### Wire format (v2, identical across sinks)

```
YYYY-MM-DD | turn=N | model=NAME | selected=PCT | spread=[N,N,N] | correction=yes|no | waited=yes|no | options=yes|no | pct=yes|no | assumed=yes|no | framing_correction=yes|no | option_modification=yes|no | task_id=ID
```

Field meanings (canonical: [`docs/telemetry-plan.md`](../../docs/telemetry-plan.md) v2):
- `selected`: confidence % of the option the user picked (0 = rejected all)
- `spread`: all confidence %s presented
- `correction` (legacy): `framing_correction OR option_modification`
- `waited`: yes if you stopped after 🛑 WAITING
- `options` / `pct`: yes if numbered options / percentages were shown
- `assumed`: yes if you stated an explicit assumption before the options
- `framing_correction`: yes if the user corrected your stated assumption
- `option_modification`: yes if the user picked an option but modified it
- `task_id`: short opaque id (≤8 alnum chars, `-` if absent) reused across confirms in one task

### Privacy contract
- ❌ No prompt content, no option text, no user identifiers
- ✅ Model name and decision metadata only
- ✅ Default mode is `off`; opt-in by config

### When to log
Only log confirmations that reflect real signal (a non-trivial decision). Skip trivial acks, status checks, and tiny clarifications.

### Example configs

**Repo with the pip CLI installed** — use `local`, picks up `copilot-confirm` from `PATH`:
```toml
# ~/.copilot-confirm/config.toml
[telemetry]
mode = "local"
path = "~/.copilot-confirm/telemetry.log"
```

**Agent environment without the pip CLI** — still use `local`; the skill's vendored `<skill_dir>/log` will be used automatically:
```toml
# ~/.copilot-confirm/config.toml
[telemetry]
mode = "local"
path = "~/some/agent/log.md"
```

**Direct file append (skip CLI subprocess)** — use `file`:
```toml
# ~/.copilot-confirm/config.toml
[telemetry]
mode = "file"
path = "~/some/agent/log.md"
```

## Bundled CLI

The skill ships a vendored copy of the telemetry CLI at `<skill_dir>/lib/copilot_confirm_telemetry/`. Invoke via `<skill_dir>/log`:

```bash
<skill_dir>/log log --model NAME --selected 70 --spread 70,25,5 \
                    --correction no --waited yes --options yes --pct yes \
                    [--assumed yes|no] [--framing-correction yes|no] \
                    [--option-modification yes|no] [--task-id ID]

<skill_dir>/log telemetry show     # display the local log
<skill_dir>/log telemetry send     # POST to configured endpoint
```

The vendored copy is byte-identical to `src/copilot_confirm/telemetry.py` in the [pip package](https://github.com/mgrandau/copilot-confirm); a CI test enforces this. Stdlib-only — no install required beyond `python3`.

## Background
Implements the concepts from Mark Grandau's article: [The Better Agent: Homing Intent Through Probabilistic Feedback](https://mgrandau.medium.com/the-better-agent-homing-intent-through-probabilistic-feedback-d545466ebe6d). The pip-installable version for GitHub Copilot in VS Code is at [mgrandau/copilot-confirm](https://github.com/mgrandau/copilot-confirm).
