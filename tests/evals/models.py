"""
Protocol-based model client for eval harness.

Abstracts away model API calls so evals can run against any model
without changing test code. Follows project's Protocol-based DI pattern.
"""

import json
import os
import subprocess
from typing import Protocol


class ModelClientProtocol(Protocol):
    """Interface for a model client that can run a prompt with instructions."""

    def complete(self, system: str, prompt: str) -> str:
        """Send prompt with system instructions, return response text."""
        ...

    @property
    def model_id(self) -> str:
        """Unique identifier for this model."""
        ...


class GitHubCopilotClient:
    """
    Model client using the GitHub Copilot CLI (`gh copilot` or `copilot-confirm`).

    Uses the `gh` CLI with a model flag when available, otherwise falls back
    to environment-based model selection.
    """

    def __init__(self, model: str) -> None:
        self._model = model

    @property
    def model_id(self) -> str:
        return self._model

    def complete(self, system: str, prompt: str) -> str:
        """
        Run completion via gh copilot suggest or similar CLI.

        Note: This is a stub — actual implementation depends on how
        the project integrates with Copilot CLI for programmatic access.
        Raises NotImplementedError until the CLI integration is confirmed.
        """
        raise NotImplementedError(
            f"GitHubCopilotClient for {self._model} not yet implemented. "
            "See issue #21 for CLI integration approach."
        )


class OpenAIClient:
    """Model client using the OpenAI API directly."""

    def __init__(self, model: str, api_key: str | None = None) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    @property
    def model_id(self) -> str:
        return self._model

    def complete(self, system: str, prompt: str) -> str:
        """Call OpenAI chat completions API via subprocess (no sdk dependency)."""
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 1000,
        }
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-X",
                "POST",
                "https://api.openai.com/v1/chat/completions",
                "-H",
                f"Authorization: Bearer {self._api_key}",
                "-H",
                "Content-Type: application/json",
                "-d",
                json.dumps(payload),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        data = json.loads(result.stdout)
        if "error" in data:
            raise RuntimeError(f"OpenAI API error: {data['error']}")
        return str(data["choices"][0]["message"]["content"])


class MockModelClient:
    """
    Mock model client for testing the harness itself.

    Returns canned responses that pass or fail specific assertions.
    """

    def __init__(self, model_id: str, response: str) -> None:
        self._model_id = model_id
        self._response = response

    @property
    def model_id(self) -> str:
        return self._model_id

    def complete(self, system: str, prompt: str) -> str:
        return self._response


# Canned responses for testing assertions
MOCK_PASSING_RESPONSE = """Here are your options:

1. Extract to dependency injection pattern (70%)
2. Use factory pattern (25%)
3. Add documentation only (5%)

🛑 WAITING
"""

MOCK_FAILING_RESPONSE = """Sure! Here's the refactored code:

```python
def process_data(data):
    return [item * 2 for item in data if item > 0]
```
"""

MOCK_PARTIAL_RESPONSE = """Here are some options:
1. Refactor using list comprehension
2. Keep current approach but add type hints

No confirmation needed, I'll go with option 1:
```python
def process_data(data):
    return [item * 2 for item in data if item > 0]
```
"""
