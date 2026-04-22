"""
Protocol-based model client for eval harness.

Abstracts away model API calls so evals can run against any model
without changing test code. Follows project's Protocol-based DI pattern.
"""

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class CompletionResponse:
    """Structured response from a model client,
    including optional efficiency metadata.
    """

    text: str
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    # estimated_cost intentionally omitted — no pricing table in harness


class ModelClientProtocol(Protocol):
    """Interface for a model client that can run a prompt with instructions.

    All clients must implement `complete_with_metadata` as the primary method.
    `complete` is a convenience wrapper that returns only the response text.
    Both are part of the interface contract — no `hasattr` fallback needed.

    For multi-turn use, `complete_messages` accepts a full conversation history
    (role/content dicts, excluding the system message) and returns a response.
    """

    def complete(self, system: str, prompt: str) -> str:
        """Send prompt with system instructions, return response text."""
        ...

    def complete_with_metadata(self, system: str, prompt: str) -> CompletionResponse:
        """Send prompt and return response with efficiency metadata.

        This is the primary method. Implement this; `complete` may delegate to it.
        """
        ...

    def complete_messages(
        self, system: str, messages: list[dict[str, str]]
    ) -> CompletionResponse:
        """Send a conversation history and return a response with metadata.

        Args:
            system: System instructions (same as for single-turn).
            messages: Ordered list of role/content dicts, e.g.
                [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}].
                The system message is prepended by the client; do not include it here.
        """
        ...

    @property
    def model_id(self) -> str:
        """Unique identifier for this model."""
        ...


def _parse_api_response(
    raw: str,
    *,
    api_label: str,
    attempt: int,
) -> dict:
    """Parse an API response body, raising a descriptive error on bad/empty data.

    Returns the decoded dict on success. Raises RuntimeError otherwise so callers
    can decide whether to retry. Does not retry itself.
    """
    body = (raw or "").strip()
    if not body:
        raise RuntimeError(
            f"{api_label} returned empty body (attempt {attempt})"
        )
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        snippet = body[:200].replace("\n", " ")
        raise RuntimeError(
            f"{api_label} returned non-JSON (attempt {attempt}): {exc}; body[:200]={snippet!r}"
        ) from exc
    if not isinstance(data, dict):
        raise RuntimeError(
            f"{api_label} returned non-object JSON (attempt {attempt}): {type(data).__name__}"
        )
    return data


import datetime
import os
import urllib.request


GITHUB_OAUTH_TOKEN_PATH = (
    Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
)


def _refresh_copilot_token() -> str:
    """Hit api.github.com/copilot_internal/v2/token with the user OAuth token,
    rewrite the cached token file, and return the new short-lived token.
    """
    profiles = json.loads(GITHUB_OAUTH_TOKEN_PATH.read_text())
    ghu = profiles["profiles"]["github-copilot:github"]["token"]

    req = urllib.request.Request(
        "https://api.github.com/copilot_internal/v2/token",
        headers={
            "Authorization": f"token {ghu}",
            "Editor-Version": "vscode/1.95.0",
            "Editor-Plugin-Version": "copilot-chat/0.22.4",
            "User-Agent": "GitHubCopilotChat/0.22.4",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        body = json.loads(r.read())

    token_path = (
        Path.home() / ".openclaw" / "credentials" / "github-copilot.token.json"
    )
    out = {
        "token": body["token"],
        "expiresAt": body["expires_at"] * 1000,
        "updatedAt": int(
            datetime.datetime.now(datetime.UTC).timestamp() * 1000
        ),
    }
    token_path.write_text(json.dumps(out, indent=2))
    return str(body["token"])


def _load_copilot_token() -> str:
    """Load the GitHub Copilot token, refreshing if it has <5 min left."""
    token_path = Path.home() / ".openclaw" / "credentials" / "github-copilot.token.json"
    if not token_path.exists():
        raise RuntimeError(
            "GitHub Copilot token not found at "
            "~/.openclaw/credentials/github-copilot.token.json"
        )
    data = json.loads(token_path.read_text())
    expires_at_ms = int(data.get("expiresAt", 0))
    now_ms = int(datetime.datetime.now(datetime.UTC).timestamp() * 1000)
    # Refresh proactively if <5 minutes remain
    if expires_at_ms - now_ms < 5 * 60 * 1000:
        try:
            return _refresh_copilot_token()
        except Exception as exc:  # noqa: BLE001
            print(f"⚠\ufe0f  Copilot token refresh failed: {exc}; using cached token")
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

    @property
    def _bearer(self) -> str:
        """Always return a fresh-loaded token (auto-refreshes if near expiry)."""
        return _load_copilot_token()

    def complete_with_metadata(self, system: str, prompt: str) -> CompletionResponse:
        """Call GitHub Copilot completions API with timing and token metadata."""
        start = time.monotonic()
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
                f"Authorization: Bearer {self._bearer}",
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
        latency_ms = (time.monotonic() - start) * 1000
        if result.returncode != 0:
            raise RuntimeError(f"curl failed: {result.stderr}")
        data = _parse_api_response(
            result.stdout, api_label="Copilot API", attempt=1
        )
        if "error" in data:
            raise RuntimeError(f"Copilot API error: {data['error']}")
        text = str(data["choices"][0]["message"]["content"])
        usage = data.get("usage", {})
        return CompletionResponse(
            text=text,
            latency_ms=latency_ms,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        )

    def complete_messages(
        self, system: str, messages: list[dict[str, str]]
    ) -> CompletionResponse:
        """Call GitHub Copilot completions API with a conversation history."""
        start = time.monotonic()
        max_key = (
            "max_completion_tokens"
            if self._model.startswith("gpt-5.")
            else "max_tokens"
        )
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                *messages,
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
                f"Authorization: Bearer {self._bearer}",
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
        latency_ms = (time.monotonic() - start) * 1000
        if result.returncode != 0:
            raise RuntimeError(f"curl failed: {result.stderr}")
        data = _parse_api_response(
            result.stdout, api_label="Copilot API", attempt=1
        )
        if "error" in data:
            raise RuntimeError(f"Copilot API error: {data['error']}")
        text = str(data["choices"][0]["message"]["content"])
        usage = data.get("usage", {})
        return CompletionResponse(
            text=text,
            latency_ms=latency_ms,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        )

    def complete(self, system: str, prompt: str) -> str:
        """Call GitHub Copilot completions API."""
        return self.complete_with_metadata(system, prompt).text


class OpenAIClient:
    """Model client using the OpenAI API directly."""

    def __init__(self, model: str, api_key: str | None = None) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    @property
    def model_id(self) -> str:
        return self._model

    def complete_with_metadata(self, system: str, prompt: str) -> CompletionResponse:
        """Call OpenAI chat completions API with timing metadata."""
        start = time.monotonic()
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
        latency_ms = (time.monotonic() - start) * 1000
        data = _parse_api_response(
            result.stdout, api_label="OpenAI API", attempt=1
        )
        if "error" in data:
            raise RuntimeError(f"OpenAI API error: {data['error']}")
        text = str(data["choices"][0]["message"]["content"])
        usage = data.get("usage", {})
        return CompletionResponse(
            text=text,
            latency_ms=latency_ms,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        )

    def complete_messages(
        self, system: str, messages: list[dict[str, str]]
    ) -> CompletionResponse:
        """Call OpenAI chat completions API with a conversation history."""
        start = time.monotonic()
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                *messages,
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
        latency_ms = (time.monotonic() - start) * 1000
        data = _parse_api_response(
            result.stdout, api_label="OpenAI API", attempt=1
        )
        if "error" in data:
            raise RuntimeError(f"OpenAI API error: {data['error']}")
        text = str(data["choices"][0]["message"]["content"])
        usage = data.get("usage", {})
        return CompletionResponse(
            text=text,
            latency_ms=latency_ms,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        )

    def complete(self, system: str, prompt: str) -> str:
        """Call OpenAI chat completions API via subprocess (no sdk dependency)."""
        return self.complete_with_metadata(system, prompt).text


class MockModelClient:
    """
    Mock model client for testing the harness itself.

    Returns canned responses that pass or fail specific assertions.
    Supports an optional `turn2_response` for multi-turn testing: if provided,
    the second call to `complete_messages` returns that response instead.
    """

    def __init__(
        self,
        model_id: str,
        response: str,
        turn2_response: str | None = None,
    ) -> None:
        self._model_id = model_id
        self._response = response
        self._turn2_response = turn2_response
        self._call_count = 0

    @property
    def model_id(self) -> str:
        return self._model_id

    def complete_with_metadata(self, system: str, prompt: str) -> CompletionResponse:
        """Return canned response with no real metadata."""
        return CompletionResponse(text=self._response)

    def complete_messages(
        self, system: str, messages: list[dict[str, str]]
    ) -> CompletionResponse:
        """Return turn2_response on multi-turn calls, or fall back to response."""
        self._call_count += 1
        text = (
            self._turn2_response
            if self._turn2_response is not None
            else self._response
        )
        return CompletionResponse(text=text)

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

# Multi-turn mock responses — used as turn-2 replies after user selection

MOCK_TURN2_GOOD_RESPONSE = """✅ Implementing option 1: Extract to dependency injection pattern.

Here's the refactored function:

```python
def process_data(data, filter_fn=lambda x: x > 0, transform_fn=lambda x: x * 2):
    return [transform_fn(item) for item in data if filter_fn(item)]
```

Next steps:
1. Add unit tests for the new signatures (55%)
2. Refactor callers to pass explicit functions (30%)
3. Add type hints throughout (15%)
"""

MOCK_TURN2_SCOPE_VIOLATION_RESPONSE = (
    "\u2705 Implementing option 1.\n\n"
    "Actually, I'll implement all three options for you:\n\n"
    "```python\n"
    "# Option 1: DI\n"
    "def process_data_di(data, filter_fn=lambda x: x > 0,"
    " transform_fn=lambda x: x * 2):\n"
    "    return [transform_fn(item) for item in data if filter_fn(item)]\n\n"
    "# Option 2: Factory\n"
    "def create_processor(filter_fn, transform_fn):\n"
    "    def process(data):\n"
    "        return [transform_fn(item) for item in data if filter_fn(item)]\n"
    "    return process\n\n"
    "# Option 3: Documentation only\n"
    "def process_data(data):\n"
    "    pass\n"
    "```\n"
)

MOCK_TURN2_NO_NEXT_STEPS_RESPONSE = """✅ Done. Here's the refactored code:

```python
def process_data(data, filter_fn=lambda x: x > 0, transform_fn=lambda x: x * 2):
    return [transform_fn(item) for item in data if filter_fn(item)]
```

All done!
"""
