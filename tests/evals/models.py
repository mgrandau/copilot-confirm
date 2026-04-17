"""
Protocol-based model client for eval harness.

Abstracts away model API calls so evals can run against any model
without changing test code. Follows project's Protocol-based DI pattern.
"""

import json
import os
import subprocess
from pathlib import Path
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


def _load_copilot_token() -> str:
    """Load the GitHub Copilot token from OpenClaw credentials."""
    token_path = Path.home() / ".openclaw" / "credentials" / "github-copilot.token.json"
    if not token_path.exists():
        raise RuntimeError(
            "GitHub Copilot token not found at ~/.openclaw/credentials/github-copilot.token.json"
        )
    data = json.loads(token_path.read_text())
    return str(data["token"])


class GitHubCopilotClient:
    """
    Model client using the GitHub Copilot API directly.

    Uses the OpenClaw-managed Copilot token to call the Copilot completions
    endpoint. No sdk dependency — stdlib + curl subprocess only.

    Confirmed working model IDs (as of 2026-04-17):
      claude-sonnet-4.6, claude-opus-4.6, claude-opus-4.7,
      gemini-2.5-pro, gemini-3.1-pro-preview, gemini-3-flash-preview,
      gpt-5-mini, gpt-4.1, gpt-5.2, gpt-5.4, gpt-5.4-mini,
      claude-haiku-4.5, grok-code-fast-1
    """

    API_URL = "https://api.githubcopilot.com/chat/completions"
    EDITOR_VERSION = "vscode/1.95.0"
    PLUGIN_VERSION = "copilot-chat/0.22.4"

    def __init__(self, model: str, token: str | None = None) -> None:
        self._model = model
        self._token = token or _load_copilot_token()

    @property
    def model_id(self) -> str:
        return self._model

    def complete(self, system: str, prompt: str) -> str:
        """Call GitHub Copilot completions API."""
        # GPT-5.x models require max_completion_tokens instead of max_tokens
        max_key = (
            "max_completion_tokens"
            if self._model.startswith("gpt-5.")
            else "max_tokens"
        )
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_key: 1000,
            "temperature": 0.0,
        }
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-X",
                "POST",
                self.API_URL,
                "-H",
                f"Authorization: Bearer {self._token}",
                "-H",
                "Content-Type: application/json",
                "-H",
                f"Editor-Version: {self.EDITOR_VERSION}",
                "-H",
                f"Editor-Plugin-Version: {self.PLUGIN_VERSION}",
                "-H",
                "Copilot-Integration-Id: vscode-chat",
                "-d",
                json.dumps(payload),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"curl failed: {result.stderr}")
        data = json.loads(result.stdout)
        if "error" in data:
            raise RuntimeError(f"Copilot API error: {data['error']}")
        return str(data["choices"][0]["message"]["content"])


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


# Model matrix for eval runs — must match OpenClaw allowed models
EVAL_MODEL_IDS = {
    "low_end": "gpt-5-mini",  # 0x free
    "haiku": "claude-haiku-4.5",  # 0.33x cheap Claude
    "baseline": "claude-sonnet-4.6",  # 1x daily driver
    "gemini_flash": "gemini-3-flash-preview",  # 0.33x cheap Gemini
    "gemini_pro": "gemini-3.1-pro-preview",  # 1x frontier Gemini
    "gpt54": "gpt-5.4",  # 1x off-scale GPT
    "heavy": "claude-opus-4.6",  # 3x heavy Claude
    "nuclear": "claude-opus-4.7",  # 7.5x nuclear
}

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
