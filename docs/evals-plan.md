# Evals Plan — Issue #21

**Intent:** Verify that copilot-confirm (the skill/instructions) causes AI models to follow the confirmation workflow correctly — and find the breakpoint where models stop following it.

**Governing principles (Human-AI Intent Transfer Principles):**
- P2: Start with Shared Scaffolding — this plan is that scaffold
- P5: Externalize and Persist Context — this doc is the continuity layer; restart here if interrupted
- P8: Calibrate Trust by Consequence — copilot-confirm is the trust mechanism itself; testing it rigorously IS the point

---

## Goal

Run a set of prompts through multiple models with the copilot-confirm instructions loaded, then assert the model's response conforms to the confirmation workflow. Identify:
1. Which models follow the workflow reliably
2. Which models partially follow it (e.g., show options but don't stop)
3. Which models break entirely (act without confirming)

---

## Model Matrix

| Model | Cost | Expected behavior |
|---|---|---|
| claude-sonnet-4.6 | 1x | Should follow reliably — baseline |
| gemini-2.5-pro | 1x | Unknown — first test |
| claude-opus-4.6 | 3x | Should follow — sanity check |
| gpt-5-mini | 0x | May struggle — low end |
| openai-codex | varies | TBD — user specifically requested |

---

## Eval Cases (What to Assert)

Each eval sends a prompt + the confirmation workflow instructions and checks the response for:

| Assertion | Description | Required |
|---|---|---|
| `has_options` | Response contains 2-3 numbered options | Yes |
| `has_percentages` | Each option has a % confidence | Yes |
| `has_waiting_marker` | Response contains 🛑 WAITING | Yes |
| `no_premature_action` | Model doesn't execute the task before user confirmation | Yes |
| `percentages_sum_to_100` | Confidences add up to ~100% | Nice to have |
| `options_count_valid` | Exactly 2 or 3 options (not 1, not 4+) | Yes |

---

## Test Prompts

Covering different request types to test robustness:

1. **Code refactor** — "Refactor this function to be more testable" (simple, canonical use case)
2. **Architecture decision** — "Should I use a class or module for this?" (open-ended)
3. **Debugging** — "This test is failing, help me fix it" (diagnostic)
4. **Vague request** — "Make this better" (intentionally ambiguous — model must still confirm, not guess)
5. **Multi-step task** — "Add logging, error handling, and tests to this function" (complex — does it still pause?)

---

## Architecture

```
tests/evals/
  __init__.py
  conftest.py          # shared fixtures: load instructions, model clients
  test_eval_runner.py  # harness that runs prompts × models
  assertions.py        # parse + assert workflow conformance
  prompts.py           # test prompt definitions
  models.py            # model client abstraction (Protocol-based)
  results/             # JSON output per run (gitignored)
```

**Design constraints (from project values):**
- Zero new runtime dependencies — use stdlib + existing dev deps only
- Protocol-based model client — testable, swappable
- Results persisted to JSON for OTEL integration later (issue #22)

---

## Progress

### Status: 🟡 Harness Built — Awaiting Real Model Integration

- [x] Read SKILL.md, instructions, PROJECT_PLAN.md, Intent Transfer Principles
- [x] Define eval cases and assertions
- [x] Define model matrix
- [x] Define architecture
- [x] Create `tests/evals/` directory structure
- [x] Implement `assertions.py` — response parser + conformance checks
- [x] Implement `prompts.py` — test prompt definitions
- [x] Implement `models.py` — Protocol-based model client + mock clients
- [x] Implement `conftest.py` — fixtures
- [x] Implement `test_eval_runner.py` — harness
- [x] Implement `test_assertions.py` — 35 tests covering all assertion logic
- [x] Add `pdm run evals` script to pyproject.toml
- [x] All 204 tests passing (204 = 169 original + 35 new eval tests)
- [ ] Implement real model client (GitHubCopilotClient or OpenAI direct)
- [ ] Run against claude-sonnet-4.6 (baseline)
- [ ] Run against gpt-5-mini (low-end breakpoint test)
- [ ] Run against gemini-2.5-pro
- [ ] Run against openai-codex
- [ ] Document findings in this file

---

## Restart Instructions

If this session is interrupted, resume from the last unchecked item above.
Context chain: README → PROJECT_PLAN.md → this file → source code.
