"""
Eval harness for copilot-confirm conformance testing.

Runs prompts through models with the confirmation workflow instructions loaded
and asserts behavioral correctness. Finds the "breakpoint" — at what model
capability level does copilot-confirm stop working?

Run with: pdm run evals
"""

import json
import sys
import time
import traceback
from pathlib import Path

from tests.evals.assertions import (
    ConformanceResult,
    FamilyRobustnessResult,
    MultiTurnResult,
    compute_family_robustness,
    evaluate_multi_turn,
    evaluate_response,
)
from tests.evals.models import (
    ModelClientProtocol,
)
from tests.evals.pricing import estimate_cost
from tests.evals.prompts import EVAL_PROMPTS, EvalPrompt

# Load the confirmation workflow instructions
INSTRUCTIONS_PATH = (
    Path(__file__).parent.parent.parent
    / "src"
    / "copilot_confirm"
    / "agent_files"
    / "instructions"
    / "confirmation_workflow.instructions.md"
)

# Phase 1: eval protocol version for result traceability
EVAL_PROTOCOL_VERSION = "1.1.0"


def load_instructions() -> str:
    """Load the copilot-confirm workflow instructions."""
    return INSTRUCTIONS_PATH.read_text()


MAX_API_RETRIES = 3
RETRY_BACKOFF_SEC = 2.0


def _with_retry(call, *, label: str):
    """Retry a model API call on transient errors with exponential backoff.

    Catches RuntimeError (raised by our parser for empty/non-JSON bodies)
    and any other exception, retrying up to MAX_API_RETRIES times.
    On final failure, re-raises the last exception.
    """
    last_exc: Exception | None = None
    for attempt in range(1, MAX_API_RETRIES + 1):
        try:
            return call()
        except Exception as exc:  # noqa: BLE001 — transient API errors
            last_exc = exc
            if attempt < MAX_API_RETRIES:
                wait = RETRY_BACKOFF_SEC * (2 ** (attempt - 1))
                print(
                    f"      \u26a0\ufe0f  {label} attempt {attempt} failed: "
                    f"{type(exc).__name__}: {exc}; retrying in {wait:.1f}s"
                )
                time.sleep(wait)
            else:
                print(
                    f"      \u274c {label} failed after {MAX_API_RETRIES} attempts: "
                    f"{type(exc).__name__}: {exc}"
                )
    assert last_exc is not None
    raise last_exc


def run_eval(
    client: ModelClientProtocol,
    prompt: EvalPrompt,
    instructions: str,
) -> ConformanceResult:
    """Run a single eval: send prompt to model, evaluate response."""
    cr = _with_retry(
        lambda: client.complete_with_metadata(
            system=instructions, prompt=prompt.prompt
        ),
        label=f"{client.model_id}/{prompt.id}",
    )

    return evaluate_response(
        model=client.model_id,
        prompt_id=prompt.id,
        response=cr.text,
        base_prompt_id=prompt.base_prompt_id,
        prompt_category=prompt.category,
        prompt_variant=prompt.variant,
        dimension_tags=prompt.dimension_tags,
        slice_tags=prompt.slice_tags,
        refusal_expected=prompt.refusal_expected,
        assumptions_required=prompt.assumptions_required,
        expected_constraints=prompt.expected_constraints,
        forbidden_behaviors=prompt.forbidden_behaviors,
        latency_ms=cr.latency_ms,
        input_tokens=cr.input_tokens,
        output_tokens=cr.output_tokens,
        total_tokens=cr.total_tokens,
        estimated_cost=estimate_cost(client.model_id, cr.input_tokens, cr.output_tokens),
    )


def run_multi_turn_eval(
    client: ModelClientProtocol,
    prompt: EvalPrompt,
    instructions: str,
    turn1_result: ConformanceResult,
) -> MultiTurnResult:
    """Run a 2-turn eval for prompts that have a multi_turn_followup.

    Turn 1 has already been executed (turn1_result provided).
    This function sends turn 2: the simulated user selection.

    Args:
        client: Model client to use.
        prompt: Prompt definition (must have multi_turn_followup set).
        instructions: System instructions.
        turn1_result: ConformanceResult from turn 1.

    Returns:
        MultiTurnResult with turn-2 response and assertions.
    """
    assert prompt.multi_turn_followup is not None, (
        f"run_multi_turn_eval called on prompt '{prompt.id}' which has no "
        "multi_turn_followup set"
    )

    selected_option = prompt.multi_turn_followup
    turn1_text = turn1_result.response

    # Build 2-turn conversation: original prompt + assistant response + user selection
    messages = [
        {"role": "user", "content": prompt.prompt},
        {"role": "assistant", "content": turn1_text},
        {"role": "user", "content": selected_option},
    ]

    cr2 = _with_retry(
        lambda: client.complete_messages(system=instructions, messages=messages),
        label=f"{client.model_id}/{prompt.id}#turn2",
    )

    return evaluate_multi_turn(
        model=client.model_id,
        prompt_id=prompt.id,
        turn1_response=turn1_text,
        turn2_response=cr2.text,
        selected_option=selected_option,
        expected_constraints=prompt.expected_constraints,
        forbidden_behaviors=prompt.forbidden_behaviors,
        original_prompt=prompt.prompt,
        turn1_result=turn1_result,
        turn2_latency_ms=cr2.latency_ms,
        turn2_input_tokens=cr2.input_tokens,
        turn2_output_tokens=cr2.output_tokens,
        turn2_total_tokens=cr2.total_tokens,
    )


def run_all_evals(
    clients: list[ModelClientProtocol],
    prompts: list[EvalPrompt] | None = None,
) -> tuple[list[ConformanceResult], list[MultiTurnResult]]:
    """Run all prompts against all models.

    Returns a tuple of (single_turn_results, multi_turn_results).
    Single-turn results are always produced for every prompt.
    Multi-turn results are additionally produced for prompts that have
    `multi_turn_followup` set.
    """
    instructions = load_instructions()
    prompts = prompts or list(EVAL_PROMPTS)
    results: list[ConformanceResult] = []
    multi_turn_results: list[MultiTurnResult] = []

    for client in clients:
        print(f"\n{'=' * 60}")
        print(f"Model: {client.model_id}")
        print("=" * 60)

        model_pass = 0
        model_total = 0

        for prompt in prompts:
            print(f"\n  Prompt: {prompt.id} ({prompt.category})")
            try:
                result = run_eval(client, prompt, instructions)
            except Exception as exc:  # noqa: BLE001 — keep run alive
                print(
                    f"  \u274c SKIP {prompt.id} \u2014 "
                    f"{type(exc).__name__}: {exc}"
                )
                traceback.print_exc()
                _save_partial(results, multi_turn_results)
                continue
            results.append(result)

            status = "\u2705 PASS" if result.passed else "\u274c FAIL"
            print(f"  {status} \u2014 score {result.score:.0%}", end="")
            if result.latency_ms is not None:
                print(f" | {result.latency_ms:.0f}ms", end="")
            if result.total_tokens is not None:
                print(f" | {result.total_tokens} tok", end="")
            print()

            for assertion in result.assertions:
                icon = "  \u2713" if assertion.passed else "  \u2717"
                print(f"    {icon} {assertion.name}: {assertion.detail}")

            if result.passed:
                model_pass += 1
            model_total += 1

            # Incremental save so a later crash doesn't lose collected data
            _save_partial(results, multi_turn_results)

            # Phase 3: run turn 2 for multi-turn prompts
            if prompt.multi_turn_followup is not None:
                print(
                    f"\n    [Multi-turn] Running turn 2 "
                    f"(user selects: {prompt.multi_turn_followup})"
                )
                try:
                    mt_result = run_multi_turn_eval(
                        client, prompt, instructions, result
                    )
                except Exception as exc:  # noqa: BLE001 — keep run alive
                    print(
                        f"    \u274c SKIP turn-2 for {prompt.id} \u2014 "
                        f"{type(exc).__name__}: {exc}"
                    )
                    traceback.print_exc()
                    _save_partial(results, multi_turn_results)
                    continue
                multi_turn_results.append(mt_result)
                t2_status = "\u2705 T2 PASS" if mt_result.turn2_passed else "\u274c T2 FAIL"
                print(
                    f"    {t2_status} \u2014 turn-2 score {mt_result.turn2_score:.0%}",
                    end="",
                )
                if mt_result.turn2_latency_ms is not None:
                    print(f" | {mt_result.turn2_latency_ms:.0f}ms", end="")
                print()
                for a in mt_result.turn2_assertions:
                    icon = "    \u2713" if a.passed else "    \u2717"
                    print(f"      {icon} {a.name}: {a.detail}")
                _save_partial(results, multi_turn_results)

        print(f"\n  Model summary: {model_pass}/{model_total} prompts passed")

    return results, multi_turn_results


def compute_all_family_aggregates(
    results: list[ConformanceResult],
) -> list[FamilyRobustnessResult]:
    """
    Compute cross-variant robustness for every (model, base_prompt_id) group.

    Families with only one variant are still included — they reflect baseline
    stability and are meaningful once more variants are added later.
    """
    # Group by (model, base_prompt_id)
    groups: dict[tuple[str, str], list[ConformanceResult]] = {}
    for r in results:
        if not r.base_prompt_id:
            continue
        key = (r.model, r.base_prompt_id)
        groups.setdefault(key, []).append(r)

    aggregates = []
    for (model, base_id), group_results in sorted(groups.items()):
        aggregates.append(
            compute_family_robustness(model, base_id, group_results)
        )
    return aggregates


_PARTIAL_RESULTS_PATH = (
    Path(__file__).parent / "results" / "partial.json"
)


def _save_partial(
    results: list[ConformanceResult],
    multi_turn_results: list[MultiTurnResult],
) -> None:
    """Best-effort incremental save so transient crashes don't lose data."""
    try:
        save_results(
            results,
            _PARTIAL_RESULTS_PATH,
            multi_turn_results=multi_turn_results,
        )
    except Exception as exc:  # noqa: BLE001 — never let save kill the run
        print(f"      \u26a0\ufe0f  partial save failed: {exc}")


def save_results(
    results: list[ConformanceResult],
    output_path: Path,
    aggregates: list[FamilyRobustnessResult] | None = None,
    multi_turn_results: list[MultiTurnResult] | None = None,
) -> None:
    """Persist results, family-level aggregates, and multi-turn results to JSON."""
    if aggregates is None:
        aggregates = compute_all_family_aggregates(results)
    data = {
        "eval_protocol_version": EVAL_PROTOCOL_VERSION,
        "aggregates": [
            {
                "model": a.model,
                "base_prompt_id": a.base_prompt_id,
                "variant_count": a.variant_count,
                "robustness_score": a.robustness_score,
                "variant_consistency_rate": a.variant_consistency_rate,
                "constraint_preservation_rate": a.constraint_preservation_rate,
                "distractor_resilience_rate": a.distractor_resilience_rate,
                "variant_ids": a.variant_ids,
                "passed_variant_ids": a.passed_variant_ids,
                "failed_variant_ids": a.failed_variant_ids,
            }
            for a in aggregates
        ],
        "results": [
            {
                "model": r.model,
                "prompt_id": r.prompt_id,
                "response": r.response,
                "base_prompt_id": r.base_prompt_id,
                "prompt_category": r.prompt_category,
                "prompt_variant": r.prompt_variant,
                "dimension_tags": list(r.dimension_tags),
                "slice_tags": list(r.slice_tags),
                "passed": r.passed,
                "task_success": r.task_success,
                "score": r.score,
                "overall_score": r.overall_score,
                "required_passed": r.required_passed,
                "process_quality_score": r.process_quality_score,
                "calibration_score": r.calibration_score,
                "risk_score": r.risk_score,
                "refusal_expected": r.refusal_expected,
                "refusal_observed": r.refusal_observed,
                "assumptions_required": r.assumptions_required,
                "assumptions_observed": r.assumptions_observed,
                "failure_modes": r.failure_modes,
                "notes": r.notes,
                "latency_ms": r.latency_ms,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "total_tokens": r.total_tokens,
                "estimated_cost": r.estimated_cost,
                "retry_count": r.retry_count,
                "assertions": [
                    {
                        "name": a.name,
                        "passed": a.passed,
                        "detail": a.detail,
                    }
                    for a in r.assertions
                ],
            }
            for r in results
        ],
        "multi_turn_results": [
            {
                "model": mt.model,
                "prompt_id": mt.prompt_id,
                "conversation_id": mt.conversation_id,
                "selected_option": mt.selected_option,
                "turn1_response": mt.turn1_response,
                "turn2_response": mt.turn2_response,
                "turn2_passed": mt.turn2_passed,
                "turn2_score": mt.turn2_score,
                "selected_option_followed": mt.selected_option_followed,
                "unselected_options_executed": mt.unselected_options_executed,
                "scope_preserved": mt.scope_preserved,
                "next_steps_quality": mt.next_steps_quality,
                "post_selection_constraints_respected": (
                    mt.post_selection_constraints_respected
                ),
                "turn2_latency_ms": mt.turn2_latency_ms,
                "turn2_input_tokens": mt.turn2_input_tokens,
                "turn2_output_tokens": mt.turn2_output_tokens,
                "turn2_total_tokens": mt.turn2_total_tokens,
                "turn2_assertions": [
                    {"name": a.name, "passed": a.passed, "detail": a.detail}
                    for a in mt.turn2_assertions
                ],
            }
            for mt in (multi_turn_results or [])
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2))
    print(f"\nResults saved to {output_path}")


def print_summary(
    results: list[ConformanceResult],
    multi_turn_results: list[MultiTurnResult] | None = None,
) -> None:
    """Print a multi-metric cross-model summary table."""
    print(f"\n{'=' * 70}")
    print("SUMMARY — copilot-confirm eval harness")
    print(f"Eval protocol version: {EVAL_PROTOCOL_VERSION}")
    print("=" * 70)

    # Group by model
    by_model: dict[str, list[ConformanceResult]] = {}
    for r in results:
        by_model.setdefault(r.model, []).append(r)

    for model, model_results in sorted(by_model.items()):
        passed = sum(1 for r in model_results if r.passed)
        total = len(model_results)
        avg_score = sum(r.score for r in model_results) / total if total else 0
        status = "✅" if passed == total else ("⚠️" if passed > 0 else "❌")

        # Dimension averages (skip None)
        def avg_dim(attr: str, mrs: list[ConformanceResult] = model_results) -> str:
            vals = [
                v
                for r in mrs
                if (v := getattr(r, attr)) is not None
            ]
            return f"{sum(vals)/len(vals):.0%}" if vals else "—"

        pq = avg_dim("process_quality_score")
        cal = avg_dim("calibration_score")
        risk = avg_dim("risk_score")

        # Efficiency
        lats = [r.latency_ms for r in model_results if r.latency_ms is not None]
        lat_str = f"{sum(lats)/len(lats):.0f}ms" if lats else "—"
        toks = [r.total_tokens for r in model_results if r.total_tokens is not None]
        tok_str = f"{sum(toks)/len(toks):.0f}tok" if toks else "—"

        print(
            f"  {status} {model}: {passed}/{total} passed "
            f"(conformance {avg_score:.0%} | process {pq} | "
            f"calibration {cal} | risk {risk} | "
            f"latency {lat_str} | tokens {tok_str})"
        )

    # Overall dimension summary across all results
    print()
    all_total = len(results)
    all_passed = sum(1 for r in results if r.passed)
    print(f"  Total: {all_passed}/{all_total} passed")

    # Category breakdown
    by_category: dict[str, list[ConformanceResult]] = {}
    for r in results:
        by_category.setdefault(r.prompt_category, []).append(r)
    if len(by_category) > 1:
        print("\n  By category:")
        for cat, cat_results in sorted(by_category.items()):
            cp = sum(1 for r in cat_results if r.passed)
            print(f"    {cat}: {cp}/{len(cat_results)} passed")

    # Phase 2: cross-variant robustness summary
    aggregates = compute_all_family_aggregates(results)
    if aggregates:
        _print_robustness_summary(aggregates)

    # Phase 3: multi-turn confirmation fidelity summary
    if multi_turn_results:
        _print_multi_turn_summary(multi_turn_results)


def _print_multi_turn_summary(multi_turn_results: list[MultiTurnResult]) -> None:
    """Print multi-turn confirmation fidelity summary grouped by model."""
    print(f"\n{'=' * 70}")
    print("MULTI-TURN FIDELITY \u2014 post-selection behavior")
    print("=" * 70)

    by_model: dict[str, list[MultiTurnResult]] = {}
    for mt in multi_turn_results:
        by_model.setdefault(mt.model, []).append(mt)

    for model, mts in sorted(by_model.items()):
        t2_passed = sum(1 for mt in mts if mt.turn2_passed)
        total = len(mts)
        avg_score = sum(mt.turn2_score for mt in mts) / total if total else 0.0
        status = "\u2705" if t2_passed == total else ("\u26a0\ufe0f" if t2_passed > 0 else "\u274c")
        print(
            f"  {status} {model}: {t2_passed}/{total} turn-2 passed"
            f" (avg score {avg_score:.0%})"
        )
        for mt in mts:
            t2_icon = "\u2713" if mt.turn2_passed else "\u2717"
            dims = []
            if mt.selected_option_followed is not None:
                dims.append(
                    f"selected={'\u2713' if mt.selected_option_followed else '\u2717'}"
                )
            if mt.unselected_options_executed is not None:
                dims.append(
                    f"unsel_exec={'\u2713' if mt.unselected_options_executed else '\u2717'}"
                )
            if mt.scope_preserved is not None:
                dims.append(
                    f"scope={'\u2713' if mt.scope_preserved else '\u2717'}"
                )
            if mt.next_steps_quality is not None:
                dims.append(
                    f"next_steps={'\u2713' if mt.next_steps_quality else '\u2717'}"
                )
            print(
                f"    {t2_icon} {mt.prompt_id} (opt={mt.selected_option}): "
                + " | ".join(dims)
            )


def _print_robustness_summary(
    aggregates: list[FamilyRobustnessResult],
) -> None:
    """Print cross-variant robustness table grouped by model."""
    print(f"\n{'=' * 70}")
    print("ROBUSTNESS — cross-variant family stability")
    print("=" * 70)

    # Group by model
    by_model: dict[str, list[FamilyRobustnessResult]] = {}
    for a in aggregates:
        by_model.setdefault(a.model, []).append(a)

    for model, model_aggs in sorted(by_model.items()):
        multi_variant = [a for a in model_aggs if a.variant_count > 1]
        all_consistent = all(a.is_fully_consistent for a in multi_variant)
        status = "✅" if (not multi_variant or all_consistent) else "⚠️"
        avg_robustness = (
            sum(a.robustness_score for a in model_aggs) / len(model_aggs)
            if model_aggs
            else 0.0
        )
        print(
            f"  {status} {model}: "
            f"robustness {avg_robustness:.0%} "
            f"({len(multi_variant)} multi-variant famil"
            f"{'y' if len(multi_variant) == 1 else 'ies'})"
        )
        for agg in sorted(model_aggs, key=lambda a: a.base_prompt_id):
            if agg.variant_count < 2:
                continue  # single-variant families — skip detail row
            icon = "✓" if agg.is_fully_consistent else "✗"
            parts = [
                f"consistency {agg.variant_consistency_rate:.0%}",
                f"robustness {agg.robustness_score:.0%}",
            ]
            if agg.constraint_preservation_rate is not None:
                parts.append(
                    f"constraints {agg.constraint_preservation_rate:.0%}"
                )
            if agg.distractor_resilience_rate is not None:
                parts.append(
                    f"distractors {agg.distractor_resilience_rate:.0%}"
                )
            print(
                f"      {icon} {agg.base_prompt_id} "
                f"({agg.variant_count} variants): "
                + " | ".join(parts)
            )
            if agg.failed_variant_ids:
                print(
                    f"          failed: {agg.failed_variant_ids}"
                )


def main() -> int:
    """
    Entry point for `pdm run evals`.

    Currently runs mock clients to validate the harness itself.
    Real model clients are added as APIs become available.
    See evals-plan.md for progress tracking.
    """
    print("copilot-confirm eval harness")
    print("Testing: workflow conformance across model capability levels")
    print()

    # Build real clients from confirmed model IDs
    from tests.evals.models import EVAL_MODEL_IDS, GitHubCopilotClient

    real_clients: list[ModelClientProtocol] = [
        GitHubCopilotClient(EVAL_MODEL_IDS["nuclear"]),  # claude-opus-4.7 (7.5x)
        GitHubCopilotClient(EVAL_MODEL_IDS["heavy"]),  # claude-opus-4.6 (3x)
        GitHubCopilotClient(EVAL_MODEL_IDS["gpt54"]),  # gpt-5.4 (1x)
        GitHubCopilotClient(
            EVAL_MODEL_IDS["gemini_pro"]
        ),  # gemini-3.1-pro-preview (1x)
        GitHubCopilotClient(EVAL_MODEL_IDS["baseline"]),  # claude-sonnet-4.6 (1x)
        GitHubCopilotClient(
            EVAL_MODEL_IDS["gemini_flash"]
        ),  # gemini-3-flash-preview (0.33x)
        GitHubCopilotClient(EVAL_MODEL_IDS["haiku"]),  # claude-haiku-4.5 (0.33x)
        GitHubCopilotClient(EVAL_MODEL_IDS["low_end"]),  # gpt-5-mini (0x)
    ]

    results, multi_turn_results = run_all_evals(real_clients)
    print_summary(results, multi_turn_results)

    results_path = Path(__file__).parent / "results" / "latest.json"
    save_results(results, results_path, multi_turn_results=multi_turn_results)

    # Exit 1 if any baseline model failed
    baseline_results = [r for r in results if "sonnet" in r.model]
    if baseline_results and not all(r.passed for r in baseline_results):
        failed = sum(1 for r in baseline_results if not r.passed)
        print(
            f"\n⚠️  Baseline (claude-sonnet-4.6) failed "
            f"{failed}/{len(baseline_results)} prompts"
        )
        return 1

    print("\n✅ Eval run complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
