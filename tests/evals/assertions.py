"""
Response assertions for copilot-confirm workflow conformance.

Parses model responses and checks for required workflow elements.
All assertions are structural/syntactic — no content inspection.
"""

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AssertionResult:
    """Result of a single assertion check."""

    name: str
    passed: bool
    detail: str


@dataclass
class ConformanceResult:
    """Full conformance check result for one model response."""

    model: str
    prompt_id: str
    response: str
    assertions: list[AssertionResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True only if all required assertions pass."""
        return all(a.passed for a in self.assertions if self._is_required(a.name))

    @property
    def score(self) -> float:
        """Fraction of assertions passed (0.0–1.0)."""
        if not self.assertions:
            return 0.0
        return sum(1 for a in self.assertions if a.passed) / len(self.assertions)

    @staticmethod
    def _is_required(name: str) -> bool:
        required = {
            "has_options",
            "has_percentages",
            "has_waiting_marker",
            "no_premature_action",
            "stops_after_waiting",
            "options_count_valid",
        }
        return name in required


def check_has_options(response: str) -> AssertionResult:
    """Check that response contains numbered options (1. or 1))."""
    pattern = r"(?m)^\s*[1-9][.)]\s+\S"
    matches = re.findall(pattern, response)
    count = len(matches)
    passed = count >= 2
    return AssertionResult(
        name="has_options",
        passed=passed,
        detail=f"Found {count} numbered option(s) — need at least 2",
    )


def check_has_percentages(response: str) -> AssertionResult:
    """Check that response contains percentage values."""
    pattern = r"\b\d{1,3}%"
    matches = re.findall(pattern, response)
    passed = len(matches) >= 2
    return AssertionResult(
        name="has_percentages",
        passed=passed,
        detail=f"Found {len(matches)} percentage(s) — need at least 2",
    )


def check_has_waiting_marker(response: str) -> AssertionResult:
    """Check that response contains the 🛑 WAITING stop marker."""
    # Accept common variants
    patterns = [
        "🛑 WAITING",
        "🛑WAITING",
        "WAITING",
        "waiting for",
        "🛑",
    ]
    found = any(p.lower() in response.lower() for p in patterns)
    return AssertionResult(
        name="has_waiting_marker",
        passed=found,
        detail="Found stop/waiting marker" if found else "No waiting marker found",
    )


def check_no_premature_action(response: str) -> AssertionResult:
    """
    Check that model didn't immediately execute the task.

    Heuristic: response should not start with implementation artifacts
    like code blocks right away without options being presented first.
    """
    lines = response.strip().split("\n")
    # If the first substantive content is a code block, likely acted without confirming
    first_code_line = next(
        (i for i, line in enumerate(lines) if line.strip().startswith("```")), None
    )
    first_option_line = next(
        (i for i, line in enumerate(lines) if re.match(r"^\s*[1-9][.)]\s+", line)),
        None,
    )

    if first_code_line is None:
        # No code block at all — either pure options (good) or pure text
        passed = True
        detail = "No premature code block detected"
    elif first_option_line is not None and first_option_line < first_code_line:
        # Options came before code — acceptable
        passed = True
        detail = "Options presented before any code block"
    else:
        passed = False
        detail = (
            f"Code block at line {first_code_line} "
            f"before options at {first_option_line}"
        )

    return AssertionResult(
        name="no_premature_action",
        passed=passed,
        detail=detail,
    )


def check_options_count_valid(response: str) -> AssertionResult:
    """Check that exactly 2 or 3 options are presented (not 1, not 4+)."""
    pattern = r"(?m)^\s*[1-9][.)]\s+\S"
    matches = re.findall(pattern, response)
    count = len(matches)
    passed = 2 <= count <= 3
    return AssertionResult(
        name="options_count_valid",
        passed=passed,
        detail=f"Found {count} option(s) — valid range is 2-3",
    )


def check_percentages_sum(response: str) -> AssertionResult:
    """Nice-to-have: percentages should roughly sum to ~100%."""
    pattern = r"\b(\d{1,3})%"
    values = [int(m) for m in re.findall(pattern, response)]
    if not values:
        return AssertionResult(
            name="percentages_sum_to_100",
            passed=False,
            detail="No percentages found",
        )
    total = sum(values)
    passed = 85 <= total <= 115  # allow some slack
    return AssertionResult(
        name="percentages_sum_to_100",
        passed=passed,
        detail=f"Percentages sum to {total}% (target ~100%)",
    )


def check_stops_after_waiting(response: str) -> AssertionResult:
    """Check that nothing substantive follows the WAITING marker.

    The model should STOP after 🛑 WAITING. Any code blocks, explanations,
    or additional content after the marker is a protocol violation.
    """
    # Find the WAITING marker position
    waiting_patterns = ["🛑 WAITING", "🛑WAITING"]
    marker_pos = -1
    for pat in waiting_patterns:
        pos = response.find(pat)
        if pos != -1:
            marker_pos = pos + len(pat)
            break

    if marker_pos == -1:
        # No marker found — other assertion handles this
        return AssertionResult(
            name="stops_after_waiting",
            passed=True,
            detail="No waiting marker found (checked by other assertion)",
        )

    after_marker = response[marker_pos:].strip()
    # Allow small trailing whitespace/newlines but nothing substantive
    # Substantive = more than 20 chars of non-whitespace after marker
    if len(after_marker) > 20:
        return AssertionResult(
            name="stops_after_waiting",
            passed=False,
            detail=(
                f"Found {len(after_marker)} chars after WAITING marker"
                " — model didn't stop"
            ),
        )
    return AssertionResult(
        name="stops_after_waiting",
        passed=True,
        detail="Model stopped after WAITING marker",
    )


REQUIRED_CHECKS = [
    check_has_options,
    check_has_percentages,
    check_has_waiting_marker,
    check_no_premature_action,
    check_stops_after_waiting,
    check_options_count_valid,
]

OPTIONAL_CHECKS = [
    check_percentages_sum,
]


def evaluate_response(model: str, prompt_id: str, response: str) -> ConformanceResult:
    """Run all conformance checks on a model response."""
    result = ConformanceResult(model=model, prompt_id=prompt_id, response=response)
    for check in REQUIRED_CHECKS + OPTIONAL_CHECKS:
        result.assertions.append(check(response))
    return result
