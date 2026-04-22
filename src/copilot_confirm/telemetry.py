#!/usr/bin/env python3
"""Telemetry module for copilot-confirm.

Captures privacy-preserving, pipe-delimited decision telemetry for AI confirmation
workflow analysis. Tracks which options were selected, spread, corrections, and
protocol compliance signals.

Schema (v2):
    date | turn | model | selected | spread | correction | waited | options | pct
         | assumed | framing_correction | option_modification | task_id

v2 added (2026-04-22): assumed, framing_correction, option_modification, task_id.
  - `assumed`: did the model state an explicit assumption before the options?
  - `framing_correction`: did the user correct the framing/assumption?
  - `option_modification`: did the user modify the chosen option in place?
  - `task_id`: short opaque id linking multi-turn confirms within one task.
The legacy `correction` field is retained and now means
`framing_correction or option_modification` (true if either occurred).

Features:
    • Config-driven: off / local / remote modes via ~/.copilot-confirm/config.toml
    • Append-only plaintext — user can inspect every line
    • Auto-generates date (today) and turn (auto-increment per day)
    • stdlib only — no new runtime dependencies
    • Protocol-based DI for full testability

Privacy:
    • No prompt content, no option text, no user identifiers
    • Date only (no time), model name in plaintext
    • Opt-in only — mode defaults to "off"
"""

import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

__all__ = [
    "TelemetryEntry",
    "TelemetryConfig",
    "TelemetryLogger",
    "FileSystemProtocol",
    "NetworkProtocol",
    "RealFileSystem",
    "RealNetwork",
    "load_config",
    "create_telemetry_logger",
]

# Schema version — bump if fields added/removed
_SCHEMA_VERSION = "v2"
_DEFAULT_CONFIG_DIR = Path.home() / ".copilot-confirm"
_DEFAULT_LOG_PATH = _DEFAULT_CONFIG_DIR / "telemetry.log"
_DEFAULT_CONFIG_PATH = _DEFAULT_CONFIG_DIR / "config.toml"


# ============================================================================
# Domain Models
# ============================================================================


@dataclass(frozen=True, slots=True)
class TelemetryEntry:
    """One recorded decision event from the copilot-confirm protocol.

    Attributes:
        model: Model identifier string (e.g. "claude-sonnet-4.6")
        selected: Confidence % of the option picked. 0 = rejected all.
        spread: List of confidence %s presented (e.g. [70, 25, 5])
        correction: True if user modified or redirected after selection.
            Retained for backward-compat; equals
            ``framing_correction or option_modification`` when those are set.
        waited: True if model stopped after 🛑 WAITING
        options: True if numbered options were presented
        pct: True if percentages were included
        assumed: True if the model stated an explicit assumption (v2)
        framing_correction: True if user corrected the model's assumption/framing (v2)
        option_modification: True if user modified the chosen option text (v2)
        task_id: Short opaque id linking multi-turn confirms within one task (v2)
        entry_date: Date of interaction. Defaults to today if None.
        turn: Step number in session day. Auto-incremented if 0.
    """

    model: str
    selected: int
    spread: list[int]
    correction: bool
    waited: bool
    options: bool
    pct: bool
    assumed: bool = False
    framing_correction: bool = False
    option_modification: bool = False
    task_id: str = ""
    entry_date: date | None = None
    turn: int = 0  # 0 = auto-assign on write

    def to_line(self, entry_date: date, turn: int) -> str:
        """Serialize to pipe-delimited plaintext line.

        Args:
            entry_date: The date to use for the entry.
            turn: The turn number to assign.

        Returns:
            str: One pipe-delimited line per current schema.
        """
        spread_str = f"[{','.join(str(p) for p in self.spread)}]"
        correction_str = "yes" if self.correction else "no"
        waited_str = "yes" if self.waited else "no"
        options_str = "yes" if self.options else "no"
        pct_str = "yes" if self.pct else "no"
        assumed_str = "yes" if self.assumed else "no"
        framing_str = "yes" if self.framing_correction else "no"
        optmod_str = "yes" if self.option_modification else "no"
        task_id_str = self.task_id or "-"
        return (
            f"{entry_date} | turn={turn} | model={self.model}"
            f" | selected={self.selected}"
            f" | spread={spread_str} | correction={correction_str}"
            f" | waited={waited_str} | options={options_str} | pct={pct_str}"
            f" | assumed={assumed_str}"
            f" | framing_correction={framing_str}"
            f" | option_modification={optmod_str}"
            f" | task_id={task_id_str}"
        )


@dataclass(frozen=True, slots=True)
class TelemetryConfig:
    """Parsed telemetry configuration.

    Attributes:
        mode: "off" | "local" | "remote"
        path: Path to telemetry log file.
        endpoint: URL for remote mode POST. Empty string = no remote.
    """

    mode: str
    path: Path
    endpoint: str


# ============================================================================
# Protocols
# ============================================================================


class FileSystemProtocol(Protocol):
    """Protocol for filesystem operations for telemetry DI."""

    def read_text(self, path: Path) -> str:
        """Read text from path. Returns empty string if not found."""
        ...

    def append_line(self, path: Path, line: str) -> None:
        """Append a line to path, creating file and parent dirs as needed."""
        ...

    def exists(self, path: Path) -> bool:
        """Return True if path exists."""
        ...

    def count_lines_for_date(self, path: Path, date_str: str) -> int:
        """Count lines in file that start with date_str. Returns 0 if not found."""
        ...


class NetworkProtocol(Protocol):
    """Protocol for network operations for telemetry DI."""

    def post(self, url: str, data: str) -> tuple[int, str]:
        """POST plaintext data to url. Returns (status_code, response_body)."""
        ...


# ============================================================================
# Real Implementations
# ============================================================================


class RealFileSystem:
    """Production filesystem implementation for telemetry."""

    def read_text(self, path: Path) -> str:  # pragma: no cover
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def append_line(self, path: Path, line: str) -> None:  # pragma: no cover
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def exists(self, path: Path) -> bool:  # pragma: no cover
        return path.exists()

    def count_lines_for_date(
        self, path: Path, date_str: str
    ) -> int:  # pragma: no cover
        if not path.exists():
            return 0
        count = 0
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.startswith(date_str):
                    count += 1
        return count


class RealNetwork:
    """Production network implementation for telemetry send."""

    def post(self, url: str, data: str) -> tuple[int, str]:  # pragma: no cover
        encoded = data.encode("utf-8")
        req = urllib.request.Request(
            url,
            data=encoded,
            headers={"Content-Type": "text/plain; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310  # nosec B310
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, str(e.reason)
        except urllib.error.URLError as e:
            return 0, str(e.reason)


# ============================================================================
# Config Parsing
# ============================================================================


def load_config(config_path: Path | None = None) -> TelemetryConfig:
    """Parse telemetry config from TOML file, using defaults if absent.

    Config location: ~/.copilot-confirm/config.toml
    Defaults: mode=off, path=~/.copilot-confirm/telemetry.log, endpoint=""

    Args:
        config_path: Path to config file. Defaults to ~/.copilot-confirm/config.toml.

    Returns:
        TelemetryConfig with parsed or default values.
    """
    if config_path is None:
        config_path = _DEFAULT_CONFIG_PATH

    defaults = TelemetryConfig(
        mode="off",
        path=_DEFAULT_LOG_PATH,
        endpoint="",
    )

    if not config_path.exists():
        return defaults

    text = config_path.read_text(encoding="utf-8")
    return _parse_toml_telemetry(text, defaults)


def _parse_toml_telemetry(text: str, defaults: TelemetryConfig) -> TelemetryConfig:
    """Parse [telemetry] section from minimal TOML text.

    We hand-parse rather than import tomllib to stay compatible with Python <3.11
    (though we target 3.13+, this keeps the parser explicit and dependency-free).

    Args:
        text: Raw TOML file content.
        defaults: Default config to fall back on.

    Returns:
        TelemetryConfig with values from [telemetry] section.
    """
    mode = defaults.mode
    path = defaults.path
    endpoint = defaults.endpoint

    in_telemetry = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "[telemetry]":
            in_telemetry = True
            continue
        if stripped.startswith("[") and stripped != "[telemetry]":
            in_telemetry = False
            continue
        if not in_telemetry or "=" not in stripped or stripped.startswith("#"):
            continue

        key, _, val = stripped.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")

        if key == "mode":
            if val in ("off", "local", "remote"):
                mode = val
        elif key == "path":
            path = Path(val).expanduser()
        elif key == "endpoint":
            endpoint = val

    return TelemetryConfig(mode=mode, path=path, endpoint=endpoint)


# ============================================================================
# Core Logger
# ============================================================================


class TelemetryLogger:
    """Logs, displays, and sends copilot-confirm decision telemetry.

    Business: Append-only log of confirmation decisions. Tracks protocol
    compliance signals (waited, options, pct) and user behavior (correction,
    selected). Supports three modes: off, local, remote.

    Attributes:
        config: Parsed telemetry configuration.
        fs: FileSystemProtocol for I/O.
        net: NetworkProtocol for HTTP sends.
    """

    def __init__(
        self,
        config: TelemetryConfig,
        fs: FileSystemProtocol,
        net: NetworkProtocol,
    ):
        self.config = config
        self.fs = fs
        self.net = net

    def log(self, entry: TelemetryEntry) -> str | None:
        """Append one pipe-delimited line to the telemetry file.

        Does nothing if mode is "off". Auto-assigns date and turn.
        If mode is "remote", also POSTs the line immediately.

        Args:
            entry: The telemetry event to record.

        Returns:
            str: The line written, or None if mode is "off".
        """
        if self.config.mode == "off":
            return None

        today = date.today()
        today_str = today.isoformat()
        turn = self.fs.count_lines_for_date(self.config.path, today_str) + 1
        line = entry.to_line(today, turn)

        self.fs.append_line(self.config.path, line)

        if self.config.mode == "remote" and self.config.endpoint:
            self.net.post(self.config.endpoint, line)

        return line

    def show(self) -> str:
        """Read and return the telemetry log contents.

        Returns:
            str: File contents, or empty string if file not found.
        """
        return self.fs.read_text(self.config.path)

    def send(self) -> tuple[bool, str]:
        """POST all telemetry lines to the configured endpoint.

        Reads the entire log and sends it. Does nothing if mode is "off"
        or no endpoint is configured.

        Returns:
            tuple[bool, str]: (success, message)
        """
        if self.config.mode == "off":
            return False, "Telemetry is disabled (mode=off)"

        if not self.config.endpoint:
            return False, "No endpoint configured"

        content = self.fs.read_text(self.config.path)
        if not content.strip():
            return False, "No telemetry data to send"

        status, body = self.net.post(self.config.endpoint, content)
        if status == 200:
            return True, f"Sent successfully (HTTP {status})"
        return False, f"Send failed (HTTP {status}): {body}"


# ============================================================================
# Factory
# ============================================================================


def create_telemetry_logger(config_path: Path | None = None) -> TelemetryLogger:
    """Create a TelemetryLogger with production dependencies.

    Args:
        config_path: Path to config file. Defaults to ~/.copilot-confirm/config.toml.

    Returns:
        TelemetryLogger ready for use.
    """
    config = load_config(config_path)
    return TelemetryLogger(
        config=config,
        fs=RealFileSystem(),
        net=RealNetwork(),
    )
