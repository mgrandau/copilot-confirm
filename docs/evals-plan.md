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

### Status: 🟢 Complete — First Run Findings Documented

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
- [x] All 204 tests passing
- [x] Implement real GitHubCopilotClient (uses OpenClaw token, no new deps)
- [x] Run against claude-sonnet-4.6 (baseline) — 3/5 ⚠️
- [x] Run against gpt-5-mini (low-end) — 5/5 ✅ (surprised!)
- [x] Run against gemini-2.5-pro — 4/5 ⚠️
- [x] Run against gemini-3-flash-preview — 5/5 ✅
- [x] Run against claude-haiku-4.5 — 5/5 ✅
- [x] Confirmed gpt-5.2-codex does NOT support chat/completions endpoint
- [ ] Run against claude-opus-4.6 or claude-opus-4.7 (heavy end)
- [ ] Investigate why vague_request fails on Sonnet + Gemini 2.5 Pro
- [ ] Consider strengthening instructions for ambiguous prompts (P7: Iterate the Intent)

---

## First Run Findings (2026-04-17)

### Results

| Model | Passed | Avg Score | Cost |
|---|---|---|---|
| gpt-5-mini | 5/5 ✅ | 100% | 0x free |
| claude-haiku-4.5 | 5/5 ✅ | 100% | 0.33x |
| gemini-3-flash-preview | 5/5 ✅ | 100% | 0.33x |
| gemini-2.5-pro | 4/5 ⚠️ | 90% | 1x |
| claude-sonnet-4.6 | 3/5 ⚠️ | 70% | 1x |

### Breakpoint
No hard breakpoint found — all tested models at least partially follow the workflow.
The **vague_request prompt** is where models fail. Ambiguous prompts trip up even
mid-tier models. This is the highest-value failure mode to address — exactly the
case where confirmation matters most.

### Key observations
- GPT-5 mini (free) and cheap models outperformed Sonnet (1x) on this workflow
- The instructions work for structured prompts; ambiguous ones expose the gap
- Sonnet failed `architecture_decision` by jumping to code instead of options
- Gemini 2.5 Pro failed `vague_request` with garbled % output (summed to 200%)

### Next investigation (P7: Iterate the Intent)
The governing aim needs refinement for ambiguous prompts. Options:
1. Strengthen the instruction for vague inputs explicitly
2. Add a vague-prompt clause: "If intent is unclear, ask one clarifying question before presenting options"
3. Test whether the failure is instruction-wording or model capability

---

## Restart Instructions

If this session is interrupted, resume from the last unchecked item above.
Context chain: README → PROJECT_PLAN.md → this file → source code.
