"""One-off runner: only the cheap models, save to a distinct file.

Used to A/B test instruction tweaks targeting cheap-model failure modes
(assumption disclosure, ambiguity hedging, option distinctness).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.evals.models import EVAL_MODEL_IDS, GitHubCopilotClient, ModelClientProtocol
from tests.evals.test_eval_runner import print_summary, run_all_evals, save_results

CHEAP_KEYS = ["haiku", "gemini_flash", "low_end"]  # claude-haiku, gemini-3-flash, gpt-5-mini


def main() -> int:
    clients: list[ModelClientProtocol] = [
        GitHubCopilotClient(EVAL_MODEL_IDS[k]) for k in CHEAP_KEYS
    ]
    print("Cheap-model eval (instruction-tweak A/B)")
    for c in clients:
        print(f"  - {c.model_id}")
    print()

    results, multi_turn_results = run_all_evals(clients)
    print_summary(results, multi_turn_results)

    out_path = Path(__file__).parent / "results" / "cheap-instruction-tweak.json"
    save_results(results, out_path, multi_turn_results=multi_turn_results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
