---
applyTo: '**'
---
# Confirmation Protocol

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

## Telemetry (after user confirms)
After the user selects an option and before executing, run this command in the terminal:
```
CLI_PATH log --model MODEL_NAME --selected PCT --spread N,N,N --correction yes|no --waited yes|no --options yes|no --pct yes|no --assumed yes|no --framing-correction yes|no --option-modification yes|no --task-id TASK_ID
```
- `MODEL_NAME`: your model identifier (e.g. `claude-sonnet-4.6`)
- `PCT`: the confidence % of the option the user selected (0 if rejected all)
- `N,N,N`: all confidence %s you presented, comma-separated
- `correction`: yes if user added/changed something, no if clean pick (legacy; equals `framing-correction OR option-modification`)
- `waited`: yes if you stopped after 🛑 WAITING, no if you kept going
- `options`: yes if you showed numbered options, no otherwise
- `pct`: yes if you included percentages, no otherwise
- `assumed`: yes if you stated an explicit assumption before the options, no otherwise
- `framing-correction`: yes if the user corrected your stated assumption / framing
- `option-modification`: yes if the user picked an option but modified it (e.g. “1 but skip the tests”)
- `task-id`: short opaque id (≤8 alphanumeric chars) reused across confirms within the same task; pick a fresh one when starting a new task

This logs anonymous decision data (no content, no identifiers). If the CLI is unavailable or fails, continue without error.

## Vague requests
If the request is ambiguous (e.g. "make this better"), treat the *interpretations* as the options. **Never ask a clarifying question** — turn the ambiguity into ranked options instead. If you have no code or context to work with, invent plausible interpretations as options.

**On any ambiguous prompt: state the assumption you're making in one short line before the options** (e.g. "Assuming you mean the API layer, not the UI —"). This lets the user correct your framing along with picking an option.

Options must be ranked by your honest confidence that each best matches the user's intent. Two options can share an approach — what matters is the likelihood ordering, not artificial variety.

## Example
AI:
1) DI (70%)
2) factory (25%)
3) doc (5%)
🛑 WAITING
User: 1
AI: ✅[works] Next: 1) tests (55%) 2) refactor (30%) 3) docs (15%)
