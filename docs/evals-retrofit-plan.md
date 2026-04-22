# Evals Retrofit Plan — HELM-Inspired Expansion for copilot-confirm

**Intent:** Upgrade the current eval harness from a narrow protocol-conformance check into a multi-dimensional evaluation system that measures **task success**, **process quality**, **robustness**, **calibration**, **risk**, and **efficiency**.

This plan preserves the current harness and extends it in phases. The current tests are useful; they are just incomplete.

---

## Why this retrofit exists

The current eval harness answers a limited question:

> Does the model produce the right confirmation-workflow shape?

That includes checks like:
- numbered options
- percentages
- `🛑 WAITING`
- no premature action
- stopping after the waiting marker

Those are necessary, but they do **not** fully answer:
- Are the options actually good?
- Does behavior hold up under prompt variation?
- Does the model behave appropriately under ambiguity or uncertainty?
- Does it resist unsafe, injected, or overreaching requests?
- Does it preserve constraints across turns?
- What does conformance cost in tokens/latency?

The HELM-style lesson is: do not evaluate agents on one dimension only. Evaluate them as **protocols under variation**.

---

## Current state summary

### What the harness already does well

Files:
- `tests/evals/prompts.py`
- `tests/evals/assertions.py`
- `tests/evals/models.py`
- `tests/evals/test_eval_runner.py`
- `docs/evals-plan.md`

Current coverage:
- Single-turn protocol conformance
- Light prompt diversity across 5 prompts
- Multi-model execution
- JSON result persistence

Current assertions:
- `has_options`
- `has_percentages`
- `has_waiting_marker`
- `no_premature_action`
- `stops_after_waiting`
- `options_count_valid`
- `percentages_sum_to_100` (optional)

### What is missing

- Process-quality scoring
- Real robustness / perturbation testing
- Calibration / ambiguity handling checks
- Risk / refusal / injection resistance checks
- Efficiency metrics
- Multi-turn confirmation fidelity
- Versioned eval protocol metadata
- Slice analysis by user/task style

---

## Design goals

1. **Keep deterministic checks first**
   Start with prompt metadata + rule-based assertions. Do not require an LLM judge for Phase 1.

2. **Preserve the existing harness**
   The current conformance checks remain valuable as the `protocol_conformance` dimension.

3. **Separate dimensions explicitly**
   Never collapse everything into a single score.

4. **Add realistic failure modes before adding more happy-path prompts**
   The biggest gains are in ambiguity, constraint flips, prompt injection, and multi-turn drift.

5. **Freeze the eval protocol version**
   Track prompt variants, instruction versions, and environment assumptions so score changes stay interpretable.

---

# Phase 1 — Expand single-turn coverage

**Goal:** Add the highest-value HELM dimensions without changing the harness architecture too much.

**Outcome:** The harness still runs as a single-turn evaluator, but it now measures:
- protocol conformance
- process quality
- calibration
- risk
- basic efficiency metadata

## Scope

### 1. Expand prompt metadata

Modify `tests/evals/prompts.py` to support richer prompt definitions.

### Current shape

```python
@dataclass(frozen=True)
class EvalPrompt:
    id: str
    category: str
    prompt: str
    description: str
```

### Target shape

```python
@dataclass(frozen=True)
class EvalPrompt:
    id: str
    base_prompt_id: str
    category: str
    variant: str | None
    prompt: str
    description: str
    dimension_tags: tuple[str, ...]
    slice_tags: tuple[str, ...] = ()
    expected_constraints: tuple[str, ...] = ()
    forbidden_behaviors: tuple[str, ...] = ()
    assumptions_required: bool = False
    refusal_expected: bool = False
    multi_turn_followup: str | None = None
```

## 2. Add new prompt categories

Add new prompts in `tests/evals/prompts.py`.

### Robustness / perturbation prompts
- `refactor_paraphrase`
- `refactor_reordered_instructions`
- `debugging_noisy_context`
- `missing_but_inferable_context`
- `malformed_but_recoverable_input`
- `distractor_context`

### Constraint / contrast prompts
- `constraint_flip`
- `wrong_tool_temptation`
- `minimal_change_vs_full_refactor`
- `do_not_edit_only_explain`
- `one_constraint_changed`

### Calibration prompts
- `ambiguous_goal_interpretations`
- `insufficient_context_bounded_assumptions`
- `impossible_request`
- `evidence_weak`
- `conflicting_requirements`

### Risk / refusal prompts
- `unsafe_request`
- `policy_violation_request`
- `prompt_injection_attempt`
- `hidden_instruction_exfiltration`
- `malicious_overreach`
- `fabrication_bait`

### Slice-analysis prompts
These are not new behaviors so much as metadata-tagged variants:
- `terse`
- `verbose`
- `novice`
- `expert`
- `non_native`
- `accessibility_style`

## 3. Add new assertions

Modify `tests/evals/assertions.py`.

### Process quality
Add deterministic checks for:
- `options_are_distinct`
- `options_match_prompt_scope`
- `options_respect_constraints`
- `confidence_ranking_consistent`
- `assumptions_disclosed_when_needed`

### Calibration
Add checks for:
- `does_not_fabricate_context`
- `does_not_overclaim_certainty`
- `ambiguity_handled_via_interpretations`
- `impossible_request_not_presented_as_executable`

### Risk
Add checks for:
- `refusal_when_required`
- `prompt_injection_resisted`
- `no_hidden_instruction_leakage`
- `no_unsafe_action_suggestion`
- `no_fake_completion_claim`
- `no_fabricated_artifacts`

## 4. Expand result schema

Modify `tests/evals/assertions.py` and `tests/evals/test_eval_runner.py` result persistence.

### Current result shape
Currently stores:
- model
- prompt_id
- passed
- score
- assertions

### Add fields
- `base_prompt_id`
- `prompt_category`
- `prompt_variant_id`
- `dimension_tags`
- `slice_tags`
- `task_success`
- `process_quality_score`
- `calibration_score`
- `risk_score`
- `overall_score`
- `required_passed`
- `refusal_expected`
- `refusal_observed`
- `assumptions_required`
- `assumptions_observed`
- `latency_ms`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `estimated_cost`
- `retry_count`
- `failure_modes`
- `notes`

## 5. Capture efficiency metadata

Modify `tests/evals/models.py` so the model client can optionally return:
- raw response text
- latency
- token usage if available
- retry count if any

If token usage is unavailable from a provider, store `None` rather than fabricating values.

## 6. Update summary output

Modify `tests/evals/test_eval_runner.py` to print a multi-metric summary rather than only pass/fail and average score.

Target summary dimensions:
- protocol conformance
- process quality
- calibration
- risk
- efficiency (when available)

## Phase 1 files to touch

- `tests/evals/prompts.py`
- `tests/evals/assertions.py`
- `tests/evals/models.py`
- `tests/evals/test_eval_runner.py`
- `tests/evals/test_assertions.py`
- `docs/evals-plan.md` (summary update after implementation)

## Phase 1 acceptance criteria

- Existing conformance checks still pass
- Prompt metadata supports dimensions/constraints/refusal flags
- At least 10 new prompts added across robustness/calibration/risk
- At least 8 new assertions added
- Results JSON includes dimension and efficiency fields
- Summary output shows more than a single score
- All tests pass via `pdm run test`

## Phase 1 risks

- Overfitting heuristics to current prompt wording
- Brittle lexical checks for scope/distinctness
- Too many prompts added before result schema is stable

## Phase 1 guardrails

- Prefer coarse, explainable heuristics over fake precision
- Add clear assertion detail strings for debugging
- Do not add LLM-as-judge yet

---

# Phase 2 — Cross-variant robustness scoring

**Goal:** Measure whether behavior is stable across prompt variants, not just valid on a single prompt.

**Outcome:** The harness can compare prompt variants belonging to the same task family and report robustness degradation.

## Scope

## 1. Add prompt families / variant groups

Extend `EvalPrompt` usage so multiple prompt variants point to the same `base_prompt_id`.

Examples:
- `refactor_simple` → base `refactor`
- `refactor_paraphrase` → base `refactor`
- `refactor_reordered_instructions` → base `refactor`

## 2. Add cross-run robustness logic

Modify `tests/evals/test_eval_runner.py` to compute family-level stability.

New aggregate metrics:
- `robustness_score`
- `variant_consistency_rate`
- `constraint_preservation_rate`
- `distractor_resilience_rate`

## 3. Add cross-run assertions / analysis helpers

Likely implemented as summary helpers rather than per-response assertions:
- `behavior_consistent_across_variants`
- `critical_constraint_preserved_under_noise`
- `malformed_input_handled_gracefully`
- `distractors_not_elevated`

## 4. Add richer results persistence

Persist both:
- per-response results
- per-family aggregate results

Potential JSON structure:
- `responses`: list of response-level results
- `aggregates`: dict keyed by model and base prompt family

## Phase 2 files to touch

- `tests/evals/prompts.py`
- `tests/evals/test_eval_runner.py`
- `tests/evals/assertions.py` (shared helper logic)
- `docs/evals-plan.md`

## Phase 2 acceptance criteria

- Prompt families are explicit and versioned
- Harness reports stability by base prompt family
- Robustness summary distinguishes single-response pass from cross-variant consistency
- Results JSON stores aggregate robustness metrics

## Phase 2 risks

- Confusing response-level and family-level scoring
- Treating any output difference as failure rather than meaningful variation

## Phase 2 guardrails

- Score consistency on key dimensions, not exact wording
- Keep family aggregation simple and explainable

---

# Phase 3 — Multi-turn confirmation fidelity

**Goal:** Verify that the protocol works after user selection, not just before it.

**Outcome:** The harness evaluates whether the model obeys the selected option, preserves constraints, avoids blending options, and proposes coherent next steps.

## Scope

## 1. Add multi-turn prompt support

Extend prompt definitions to include optional turn-2 follow-up messages.

Examples:
- model gives 3 options
- simulated user chooses `2`
- harness sends follow-up turn and evaluates the response

## 2. Add multi-turn result metadata

Result fields to support:
- `turn_index`
- `conversation_id`
- `selected_option`
- `selected_option_followed`
- `unselected_options_executed`
- `scope_preserved`
- `next_steps_quality`

## 3. Add multi-turn assertions

Add checks for:
- `selected_option_followed`
- `unselected_options_not_executed`
- `scope_preserved_after_selection`
- `next_steps_are_follow_on_not_reset`
- `post_selection_constraints_respected`

## 4. Add a conversation runner abstraction

Current `client.complete(system, prompt)` is single-turn only.

Add an interface that can support either:
- repeated chat-completion calls with message history, or
- a dedicated `complete_messages(messages)` style method

This should be introduced without breaking the existing single-turn runner.

## Phase 3 files to touch

- `tests/evals/prompts.py`
- `tests/evals/models.py`
- `tests/evals/test_eval_runner.py`
- `tests/evals/assertions.py`
- `tests/evals/test_assertions.py`
- `docs/evals-plan.md`

## Phase 3 acceptance criteria

- Harness supports at least one two-turn conversation path
- User selection is simulated deterministically
- Assertions verify execution aligns with the selected option
- Next-step quality is evaluated separately from first-turn conformance
- Results distinguish turn 1 vs turn 2 failures

## Phase 3 risks

- Overcomplicating the harness before Phase 1/2 settle
- Ambiguous evaluation of option-following without a structured parser

## Phase 3 guardrails

- Start with 2-turn only; do not build a general dialogue simulator yet
- Prefer simple deterministic cases first

---

# Scoring model

Do **not** use one blended leaderboard number as the primary output.

## Required scorecard

Every summary should report at least:
- `protocol_conformance_rate`
- `process_quality_score`
- `robustness_score`
- `calibration_score`
- `risk_score`
- `safety_violation_rate`
- `clarification_or_assumption_handling_rate`
- `cost` / `latency` when available

## Failure mode taxonomy

Use explicit failure types rather than only pass/fail.

Suggested failure modes:
- `format_violation`
- `premature_action`
- `scope_violation`
- `constraint_violation`
- `calibration_failure`
- `risk_failure`
- `fabrication`
- `prompt_injection_failure`
- `multi_turn_drift`

---

# Versioning and protocol freeze

Because prompting changes can dominate results, track versioned eval state.

## Add metadata capture for:
- eval plan version
- prompt version
- instruction file hash or version marker
- model ID
- environment assumptions
- retry policy
- stop conditions

This metadata should be saved with results so score changes are interpretable later.

---

# Suggested implementation order

## Step 1 — Phase 1 foundation
1. Expand `EvalPrompt`
2. Expand `ConformanceResult`
3. Add 10–15 high-value prompts
4. Add 8–12 high-value assertions
5. Persist new fields to JSON
6. Update tests

## Step 2 — Phase 2 robustness aggregation
1. Group prompts by `base_prompt_id`
2. Add family-level metrics
3. Persist aggregate robustness results
4. Update summaries

## Step 3 — Phase 3 multi-turn support
1. Introduce conversation-capable model client interface
2. Add two-turn prompt cases
3. Add selected-option fidelity assertions
4. Add turn-aware summaries

---

# Orchestration plan

If implementation is delegated to a coding agent session, execute in this order:

## Work package A — Phase 1 schema + prompts
Files:
- `tests/evals/prompts.py`
- `tests/evals/assertions.py`
- `tests/evals/test_assertions.py`

## Work package B — Phase 1 runner + results
Files:
- `tests/evals/models.py`
- `tests/evals/test_eval_runner.py`

## Work package C — Phase 2 robustness aggregation
Files:
- `tests/evals/test_eval_runner.py`
- `tests/evals/prompts.py`

## Work package D — Phase 3 multi-turn support
Files:
- `tests/evals/models.py`
- `tests/evals/test_eval_runner.py`
- `tests/evals/assertions.py`

Recommended execution style:
- keep one orchestrator session in the repo
- assign one coherent work package at a time
- run `pdm run test` after each package
- update `docs/evals-plan.md` only after code lands and behavior is confirmed

---

# Definition of done

This retrofit is done when:

1. The harness reports more than protocol shape conformance
2. Robustness is measured across prompt variants, not only isolated prompts
3. Ambiguity and risk behaviors are evaluated directly
4. Multi-turn confirmation fidelity is tested
5. Results are versioned and interpretable over time
6. The repo can answer not only:
   - "Did the model follow copilot-confirm?"
   but also:
   - "How reliably does it follow the protocol under ambiguity, variation, and pressure?"

---

# Recommended next action

Start with **Phase 1 only**.

Reason:
- It delivers the highest value with the least architectural churn.
- It creates the metadata and result schema that Phase 2 and Phase 3 depend on.
- It keeps the harness understandable while making it meaningfully better.
