"""
Eval harness for copilot-confirm conformance testing.

Runs prompts through models with the confirmation workflow instructions loaded
and asserts behavioral correctness. Finds the "breakpoint" — at what model
capability level does copilot-confirm stop working?

Run with: pdm run evals
"""

import json
import sys
from pathlib import Path

from tests.evals.assertions import ConformanceResult, evaluate_response
from tests.evals.models import (
    MOCK_FAILING_RESPONSE,
    MOCK_PASSING_RESPONSE,
    MOCK_PARTIAL_RESPONSE,
    MockModelClient,
    ModelClientProtocol,
)
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


def load_instructions() -> str:
    """Load the copilot-confirm workflow instructions."""
    return INSTRUCTIONS_PATH.read_text()


def run_eval(
    client: ModelClientProtocol,
    prompt: EvalPrompt,
    instructions: str,
) -> ConformanceResult:
    """Run a single eval: send prompt to model, evaluate response."""
    response = client.complete(system=instructions, prompt=prompt.prompt)
    return evaluate_response(
        model=client.model_id,
        prompt_id=prompt.id,
        response=response,
    )


def run_all_evals(
    clients: list[ModelClientProtocol],
    prompts: list[EvalPrompt] | None = None,
) -> list[ConformanceResult]:
    """Run all prompts against all models."""
    instructions = load_instructions()
    prompts = prompts or list(EVAL_PROMPTS)
    results = []

    for client in clients:
        print(f"\n{'='*60}")
        print(f"Model: {client.model_id}")
        print("=" * 60)

        model_pass = 0
        model_total = 0

        for prompt in prompts:
            print(f"\n  Prompt: {prompt.id} ({prompt.category})")
            result = run_eval(client, prompt, instructions)
            results.append(result)

            status = "✅ PASS" if result.passed else "❌ FAIL"
            print(f"  {status} — score {result.score:.0%}")

            for assertion in result.assertions:
                icon = "  ✓" if assertion.passed else "  ✗"
                print(f"    {icon} {assertion.name}: {assertion.detail}")

            if result.passed:
                model_pass += 1
            model_total += 1

        print(f"\n  Model summary: {model_pass}/{model_total} prompts passed")

    return results


def save_results(results: list[ConformanceResult], output_path: Path) -> None:
    """Persist results to JSON for OTEL integration (issue #22)."""
    data = [
        {
            "model": r.model,
            "prompt_id": r.prompt_id,
            "passed": r.passed,
            "score": r.score,
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
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2))
    print(f"\nResults saved to {output_path}")


def print_summary(results: list[ConformanceResult]) -> None:
    """Print a cross-model summary table."""
    print(f"\n{'='*60}")
    print("SUMMARY")
    print("=" * 60)

    # Group by model
    by_model: dict[str, list[ConformanceResult]] = {}
    for r in results:
        by_model.setdefault(r.model, []).append(r)

    for model, model_results in sorted(by_model.items()):
        passed = sum(1 for r in model_results if r.passed)
        total = len(model_results)
        avg_score = sum(r.score for r in model_results) / total if total else 0
        status = "✅" if passed == total else ("⚠️" if passed > 0 else "❌")
        print(f"  {status} {model}: {passed}/{total} passed (avg score {avg_score:.0%})")


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

    # Start with mock clients to validate harness logic
    clients: list[ModelClientProtocol] = [
        MockModelClient("mock/passing", MOCK_PASSING_RESPONSE),
        MockModelClient("mock/failing", MOCK_FAILING_RESPONSE),
        MockModelClient("mock/partial", MOCK_PARTIAL_RESPONSE),
    ]

    results = run_all_evals(clients)
    print_summary(results)

    results_path = Path(__file__).parent / "results" / "latest.json"
    save_results(results, results_path)

    # Exit 1 if any passing mock failed (harness self-test)
    mock_pass_results = [r for r in results if r.model == "mock/passing"]
    if not all(r.passed for r in mock_pass_results):
        print("\n❌ Harness self-test failed — mock/passing model didn't pass all assertions")
        return 1

    print("\n✅ Harness self-test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
