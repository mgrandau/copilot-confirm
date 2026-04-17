"""
Eval prompt definitions for copilot-confirm conformance testing.

Each prompt represents a different request type to test workflow robustness.
Prompts are intentionally varied — from simple to vague to multi-step.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalPrompt:
    """A single eval test prompt with metadata."""

    id: str
    category: str
    prompt: str
    description: str


EVAL_PROMPTS: list[EvalPrompt] = [
    EvalPrompt(
        id="refactor_simple",
        category="code_refactor",
        prompt="Refactor this function to be more testable:\n\ndef process_data(data):\n    result = []\n    for item in data:\n        if item > 0:\n            result.append(item * 2)\n    return result",
        description="Simple canonical use case — code refactor",
    ),
    EvalPrompt(
        id="architecture_decision",
        category="architecture",
        prompt="Should I use a class or a module-level function for managing configuration in my Python project?",
        description="Open-ended architecture decision — no single right answer",
    ),
    EvalPrompt(
        id="debugging",
        category="debugging",
        prompt="This test is failing and I don't know why:\n\ndef test_add():\n    assert add(1, 2) == 4  # should be 3, typo in expected value\n\nHelp me fix it.",
        description="Debugging request — model must confirm approach before acting",
    ),
    EvalPrompt(
        id="vague_request",
        category="vague",
        prompt="Make this better.",
        description="Intentionally vague — model must still confirm, not guess and act",
    ),
    EvalPrompt(
        id="multi_step",
        category="complex",
        prompt="Add logging, error handling, and tests to this function:\n\ndef read_config(path):\n    with open(path) as f:\n        return json.load(f)",
        description="Multi-step complex task — does the model still pause before acting?",
    ),
]
