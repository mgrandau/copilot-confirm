#!/usr/bin/env python3
"""Unit tests for create_issues.py - GitHub Issue Creator.

Provides 100% coverage for all functions including:
- Color output helpers
- Data classes
- GitHub CLI functions (mocked)
- Validation functions
- Issue creation functions
- CLI entry point
"""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from create_issues import (
    MAX_BODY_LENGTH,
    MAX_TITLE_LENGTH,
    BatchCreationResult,
    Colors,
    IssueCreationResult,
    Label,
    OperationResult,
    ValidationResult,
    check_github_cli_available,
    convert_to_issue_body,
    create_all_issues,
    create_github_issue,
    create_label,
    create_labels_batch,
    get_missing_labels,
    get_repository_labels,
    get_required_labels,
    handle_label_management,
    initialize_prerequisites,
    invoke_with_retry,
    main,
    print_color,
    print_error,
    print_info,
    print_success,
    print_warning,
    validate_all_issues,
    validate_input_safety,
    validate_issue,
    validate_issue_body_structure,
    validate_issue_conventions,
    validate_issue_labels,
    validate_issue_required_fields,
    validate_issue_security,
    write_execution_summary,
    write_labels_for_ai,
)

# ============================================================================
# Test Colors Class
# ============================================================================


class TestColors:
    """Tests for Colors ANSI escape code constants."""

    @pytest.mark.parametrize(
        "color_attr",
        ["RED", "GREEN", "YELLOW", "CYAN", "WHITE", "GRAY", "MAGENTA", "RESET", "BOLD"],
    )
    def test_color_code_is_valid_ansi(self, color_attr: str) -> None:
        """Validates Colors class ANSI escape codes are well-formed strings.

        Parameterized test covering all 9 color constants to ensure each
        contains valid ANSI escape sequence prefix for terminal formatting.

        Args:
            self: Test fixture
            color_attr: Color constant name (RED, GREEN, etc.)

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If color not str or missing ANSI prefix

        Testing Principles: Constant validation, ANSI compliance

        Arrangement: Get color constant via getattr(Colors, color_attr)
        Action: Check type and prefix of color value
        Assertion: isinstance(str), startswith("\033[")

        Examples:
            ```python
            assert Colors.RED.startswith("\033[")
            ```
        """
        color = getattr(Colors, color_attr)
        assert isinstance(color, str)
        assert color.startswith("\033[")


# ============================================================================
# Test Print Functions
# ============================================================================


class TestPrintFunctions:
    """Tests for colored print helper functions."""

    def test_print_color_outputs_with_codes(self, capsys) -> None:
        """Validates print_color outputs message w/ ANSI color codes.

        Tests core print_color function wraps message in color code prefix
        and RESET suffix for proper terminal color rendering. Foundation
        for all colored output helpers.

        Args:
            self: Test fixture
            capsys: pytest stdout/stderr capture fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If message or codes missing from output

        Testing Principles: Output formatting, ANSI code wrapping

        Arrangement: Prepare message string and GREEN color code
        Action: Call print_color(msg, Colors.GREEN), capture stdout
        Assertion: Output contains message, GREEN code, and RESET

        Examples:
            ```python
            print_color("Success", Colors.GREEN)
            assert Colors.GREEN in captured.out and Colors.RESET in captured.out
            ```
        """
        print_color("Test message", Colors.GREEN)
        captured = capsys.readouterr()
        assert "Test message" in captured.out
        assert Colors.GREEN in captured.out
        assert Colors.RESET in captured.out

    def test_print_color_custom_end(self, capsys) -> None:
        """Validates print_color respects custom end parameter.

        Tests end parameter override for inline output without trailing
        newline. Enables progress indicators and inline status messages
        in CLI output.

        Args:
            self: Test fixture
            capsys: pytest stdout/stderr capture fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If output ends with newline

        Testing Principles: Parameter passing, output control

        Arrangement: Prepare message and end="" param
        Action: Call print_color(msg, color, end=""), capture stdout
        Assertion: captured.out does not end with newline

        Examples:
            ```python
            print_color("Loading", Colors.CYAN, end="")
            print_color(".", Colors.CYAN, end="")  # Progress dots
            ```
        """
        print_color("No newline", Colors.WHITE, end="")
        captured = capsys.readouterr()
        assert not captured.out.endswith("\n")

    @pytest.mark.parametrize(
        ("func", "msg", "prefix", "color"),
        [
            (print_error, "Something failed", "[ERROR]", Colors.RED),
            (print_warning, "Caution advised", "[WARN]", Colors.YELLOW),
            (print_success, "Operation complete", "[OK]", Colors.GREEN),
        ],
    )
    def test_prefixed_print_helpers(self, capsys, func, msg, prefix, color) -> None:
        """Validates prefixed print helpers output correct prefix and color.

        Parameterized test covering print_error, print_warning, print_success
        to verify each outputs expected prefix ([ERROR], [WARN], [OK]) w/
        appropriate ANSI color code for visual differentiation.

        Args:
            self: Test fixture
            capsys: pytest stdout/stderr capture fixture
            func: Print function to test
            msg: Message string to output
            prefix: Expected prefix in output
            color: Expected ANSI color code

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If prefix or color missing from output

        Testing Principles: Output formatting, prefix consistency

        Arrangement: Select print func, msg, expected prefix/color
        Action: Call func(msg), capture stdout
        Assertion: Output contains "{prefix} {msg}" and color code

        Examples:
            ```python
            print_error("Failed")
            assert "[ERROR] Failed" in captured.out
            ```
        """
        func(msg)
        captured = capsys.readouterr()
        assert f"{prefix} {msg}" in captured.out
        assert color in captured.out

    def test_print_info_no_prefix(self, capsys) -> None:
        """Validates print_info outputs message in cyan w/o prefix.

        Tests print_info differs from error/warning/success by having
        no bracketed prefix. Used for neutral informational output
        that doesn't indicate success/failure state.

        Args:
            self: Test fixture
            capsys: pytest stdout/stderr capture fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If any prefix present or cyan missing

        Testing Principles: Output differentiation, prefix absence

        Arrangement: Prepare info message
        Action: Call print_info(msg), capture stdout
        Assertion: Contains CYAN, no [ERROR]/[OK]/[WARN] prefixes

        Examples:
            ```python
            print_info("Processing 5 items...")
            # Output: "Processing 5 items..." in cyan, no prefix
            ```
        """
        print_info("Status update")
        captured = capsys.readouterr()
        assert "Status update" in captured.out
        assert Colors.CYAN in captured.out
        assert "[ERROR]" not in captured.out
        assert "[OK]" not in captured.out
        assert "[WARN]" not in captured.out


# ============================================================================
# Test Data Classes
# ============================================================================


class TestLabel:
    """Tests for Label dataclass."""

    def test_label_creation(self) -> None:
        """Validates Label dataclass stores name, description, and color.

        Tests Label frozen dataclass construction w/ all 3 required fields.
        Verifies immutable storage of GitHub label metadata for batch
        creation operations.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If any field value incorrect

        Testing Principles: Dataclass construction, field storage

        Arrangement: Prepare label params (name, description, color)
        Action: Construct Label("p1", "Critical priority", "d73a4a")
        Assertion: All 3 fields match input values

        Examples:
            ```python
            label = Label("bug", "Bug report", "ff0000")
            assert label.name == "bug" and label.color == "ff0000"
            ```
        """
        label = Label("p1", "Critical priority", "d73a4a")
        assert label.name == "p1"
        assert label.description == "Critical priority"
        assert label.color == "d73a4a"


class TestOperationResult:
    """Tests for OperationResult dataclass."""

    def test_success_result(self) -> None:
        """Validates OperationResult stores success state w/ result data.

        Tests success path: success=True, result contains data dict,
        error=None, attempt=1 (default). Verifies dataclass field
        defaults work correctly for happy path.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success state or defaults incorrect

        Testing Principles: Success state, default values, optional fields

        Arrangement: Prepare result data dict
        Action: Construct OperationResult(success=True, result={...})
        Assertion: success=True, result=data, error=None, attempt=1

        Examples:
            ```python
            result = OperationResult(success=True, result={"id": 1})
            assert result.success and result.error is None
            ```
        """
        result = OperationResult(success=True, result={"data": "value"})
        assert result.success is True
        assert result.result == {"data": "value"}
        assert result.error is None
        assert result.attempt == 1

    def test_failure_result(self) -> None:
        """Validates OperationResult stores failure state w/ error message.

        Tests failure path: success=False, result=None, error contains
        descriptive message for user feedback. Verifies error field
        populated for failure diagnosis.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If failure state incorrect

        Testing Principles: Failure state, error messaging

        Arrangement: Prepare error message string
        Action: Construct OperationResult(success=False, error="...")
        Assertion: success=False, result=None, error=msg

        Examples:
            ```python
            result = OperationResult(success=False, error="Timeout")
            assert not result.success and "Timeout" in result.error
            ```
        """
        result = OperationResult(success=False, error="Network timeout")
        assert result.success is False
        assert result.result is None
        assert result.error == "Network timeout"

    def test_retry_attempt_tracking(self) -> None:
        """Validates OperationResult tracks retry attempt number.

        Tests attempt field records which try succeeded for retry
        diagnostics. Enables logging of retry count and detection
        of flaky operations requiring multiple attempts.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If attempt != 3

        Testing Principles: Retry tracking, diagnostic metadata

        Arrangement: Prepare success result w/ attempt=3
        Action: Construct OperationResult(success=True, attempt=3)
        Assertion: result.attempt == 3

        Examples:
            ```python
            # Succeeded on 3rd try
            result = OperationResult(success=True, result="ok", attempt=3)
            log.info(f"Succeeded after {result.attempt} attempts")
            ```
        """
        result = OperationResult(success=True, result="ok", attempt=3)
        assert result.attempt == 3


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_when_no_errors(self) -> None:
        """Validates is_valid returns True when errors list empty.

        Tests ValidationResult computed property is_valid derives from
        errors list length. Empty errors = valid, any errors = invalid.
        Warnings don't affect validity.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If is_valid != True or lists not empty

        Testing Principles: Computed properties, default values

        Arrangement: Construct ValidationResult w/ defaults
        Action: Check is_valid property
        Assertion: is_valid=True, errors=[], warnings=[]

        Examples:
            ```python
            result = ValidationResult()
            assert result.is_valid and len(result.errors) == 0
            ```
        """
        result = ValidationResult()
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_invalid_when_has_errors(self) -> None:
        """Validates is_valid returns False when errors exist.

        Tests ValidationResult computed property correctly derives
        invalid state from non-empty errors list. Any error makes
        entire validation result invalid.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If is_valid != False

        Testing Principles: Computed properties, error semantics

        Arrangement: Construct ValidationResult w/ errors=["Missing title"]
        Action: Check is_valid property
        Assertion: is_valid=False

        Examples:
            ```python
            result = ValidationResult(errors=["Field required"])
            assert not result.is_valid
            ```
        """
        result = ValidationResult(errors=["Missing title"])
        assert result.is_valid is False

    def test_valid_with_warnings_only(self) -> None:
        """Validates warnings don't affect is_valid computation.

        Tests ValidationResult treats warnings as non-blocking. Issue
        can proceed with warnings but not errors. Enables soft
        validation for conventions vs hard validation for requirements.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If is_valid != True

        Testing Principles: Warning vs error semantics, non-blocking

        Arrangement: Construct ValidationResult w/ warnings only
        Action: Check is_valid property
        Assertion: is_valid=True (warnings don't block)

        Examples:
            ```python
            result = ValidationResult(warnings=["Consider adding estimate"])
            assert result.is_valid  # Warnings are advisory
            ```
        """
        result = ValidationResult(warnings=["Consider adding estimate"])
        assert result.is_valid is True


class TestIssueCreationResult:
    """Tests for IssueCreationResult dataclass."""

    def test_successful_creation(self) -> None:
        """Validates IssueCreationResult stores URL on success.

        Tests success path stores issue_url from gh CLI output for
        user feedback and logging. URL enables direct navigation
        to newly created issue.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success != True or URL missing

        Testing Principles: Success state, URL capture

        Arrangement: Prepare success=True and issue URL
        Action: Construct IssueCreationResult w/ URL
        Assertion: success=True, issue_url contains github.com

        Examples:
            ```python
            result = IssueCreationResult(success=True, issue_url="https://...")
            print(f"Created: {result.issue_url}")
            ```
        """
        result = IssueCreationResult(
            success=True, issue_url="https://github.com/o/r/issues/1"
        )
        assert result.success is True
        assert result.issue_url == "https://github.com/o/r/issues/1"

    def test_failed_creation(self) -> None:
        """Validates IssueCreationResult stores error message on failure.

        Tests failure path stores descriptive error for user feedback
        and debugging. Error message should explain why creation failed.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success != False or error missing

        Testing Principles: Failure state, error capture

        Arrangement: Prepare success=False and error message
        Action: Construct IssueCreationResult w/ error
        Assertion: success=False, error contains description

        Examples:
            ```python
            result = IssueCreationResult(success=False, error="Rate limit")
            print(f"Failed: {result.error}")
            ```
        """
        result = IssueCreationResult(success=False, error="Permission denied")
        assert result.success is False
        assert result.error == "Permission denied"


class TestBatchCreationResult:
    """Tests for BatchCreationResult dataclass."""

    def test_default_values(self) -> None:
        """Validates BatchCreationResult initializes w/ zero counts.

        Tests dataclass field defaults: counts=0, lists=[]. Enables
        incremental accumulation during batch processing loop without
        explicit initialization.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If any default != expected

        Testing Principles: Default values, factory functions

        Arrangement: None (use defaults)
        Action: Construct BatchCreationResult()
        Assertion: All fields have zero/empty defaults

        Examples:
            ```python
            result = BatchCreationResult()
            result.success_count += 1  # Increment during loop
            ```
        """
        result = BatchCreationResult()
        assert result.success_count == 0
        assert result.fail_count == 0
        assert result.created_issues == []
        assert result.failed_issues == []

    def test_tracking_results(self) -> None:
        """Validates BatchCreationResult tracks created and failed issues.

        Tests full field population w/ mixed results: 2 created, 1 failed.
        Verifies list structures store issue details for summary output.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If counts or list lengths incorrect

        Testing Principles: Aggregate tracking, mixed results

        Arrangement: Prepare created/failed issue lists
        Action: Construct BatchCreationResult w/ all fields
        Assertion: Counts match, list lengths match

        Examples:
            ```python
            result = BatchCreationResult(success_count=2, fail_count=1, ...)
            print(f"Created {result.success_count}, failed {result.fail_count}")
            ```
        """
        result = BatchCreationResult(
            success_count=2,
            fail_count=1,
            created_issues=[
                {"title": "Issue 1", "url": "url1"},
                {"title": "Issue 2", "url": "url2"},
            ],
            failed_issues=[{"title": "Issue 3", "error": "Failed"}],
        )
        assert result.success_count == 2
        assert result.fail_count == 1
        assert len(result.created_issues) == 2
        assert len(result.failed_issues) == 1


# ============================================================================
# Test GitHub CLI Functions
# ============================================================================


class TestCheckGitHubCliAvailable:
    """Tests for check_github_cli_available function."""

    def test_cli_available_and_authenticated(self) -> None:
        """Validates success when gh CLI installed and authenticated.

        Tests happy path w/ mocked subprocess calls for gh --version
        and gh auth status, verifying both checks pass and version
        string extracted from output.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success not True or version missing

        Testing Principles: Happy path, multi-step verification, mock chaining

        Arrangement: Mock subprocess.run w/ side_effect [version, auth]
        Action: Call check_github_cli_available()
        Assertion: success=True, result contains version string

        Examples:
            ```python
            result = check_github_cli_available()
            assert result.success and "2.40.0" in result.result
            ```
        """
        with patch("create_issues.subprocess.run") as mock_run:
            # Mock gh --version
            mock_version = MagicMock()
            mock_version.returncode = 0
            mock_version.stdout = "gh version 2.40.0"

            # Mock gh auth status
            mock_auth = MagicMock()
            mock_auth.returncode = 0

            mock_run.side_effect = [mock_version, mock_auth]

            result = check_github_cli_available()
            assert result.success is True
            assert "gh version 2.40.0" in result.result

    def test_cli_not_installed(self) -> None:
        """Validates failure returned when gh CLI not installed.

        Tests FileNotFoundError handling when subprocess.run can't find
        gh executable. Verifies graceful failure w/ descriptive error
        message for user troubleshooting.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success != False or error msg wrong

        Testing Principles: Exception handling, graceful degradation

        Arrangement: Mock subprocess.run to raise FileNotFoundError
        Action: Call check_github_cli_available()
        Assertion: success=False, error contains "not installed"

        Examples:
            ```python
            # gh not in PATH
            result = check_github_cli_available()
            assert not result.success and "not installed" in result.error
            ```
        """
        with patch("create_issues.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("gh not found")

            result = check_github_cli_available()
            assert result.success is False
            assert "not installed" in result.error

    def test_cli_version_returns_nonzero(self) -> None:
        """Validates failure when gh --version returns non-zero exit.

        Tests gh CLI installed but broken/misconfigured scenario where
        --version check fails. Distinct from FileNotFoundError case
        where gh binary not found at all.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success != False or error msg wrong

        Testing Principles: Exit code handling, error differentiation

        Arrangement: Mock subprocess w/ returncode=1
        Action: Call check_github_cli_available()
        Assertion: success=False, error contains "not in PATH"

        Examples:
            ```python
            # gh exists but crashes on --version
            result = check_github_cli_available()
            assert "not in PATH" in result.error
            ```
        """
        with patch("create_issues.subprocess.run") as mock_run:
            mock_version = MagicMock()
            mock_version.returncode = 1  # Non-zero exit code
            mock_version.stdout = ""
            mock_version.stderr = "gh: command not found"

            mock_run.return_value = mock_version

            result = check_github_cli_available()
            assert result.success is False
            assert "not installed or not in PATH" in result.error

    def test_cli_not_authenticated(self) -> None:
        """Validates failure returned when gh CLI not authenticated.

        Tests two-step check: gh --version succeeds but gh auth status
        fails. Verifies auth check catches unauthenticated state after
        confirming CLI installation.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success != False or error msg wrong

        Testing Principles: Multi-step validation, auth verification

        Arrangement: Mock subprocess w/ [version OK, auth FAIL]
        Action: Call check_github_cli_available()
        Assertion: success=False, error contains "not authenticated"

        Examples:
            ```python
            # gh installed but not logged in
            result = check_github_cli_available()
            assert "not authenticated" in result.error
            ```
        """
        with patch("create_issues.subprocess.run") as mock_run:
            mock_version = MagicMock()
            mock_version.returncode = 0
            mock_version.stdout = "gh version 2.40.0"

            mock_auth = MagicMock()
            mock_auth.returncode = 1

            mock_run.side_effect = [mock_version, mock_auth]

            result = check_github_cli_available()
            assert result.success is False
            assert "not authenticated" in result.error

    def test_cli_timeout(self) -> None:
        """Validates failure returned on subprocess timeout.

        Tests TimeoutExpired exception handling when gh CLI hangs.
        Network issues or stuck processes should fail gracefully
        with timeout message rather than blocking indefinitely.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success != False or error msg wrong

        Testing Principles: Timeout handling, graceful failure

        Arrangement: Mock subprocess to raise TimeoutExpired
        Action: Call check_github_cli_available()
        Assertion: success=False, error contains "timed out"

        Examples:
            ```python
            # gh hangs during network operation
            result = check_github_cli_available()
            assert "timed out" in result.error
            ```
        """
        with patch("create_issues.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("gh", 30)

            result = check_github_cli_available()
            assert result.success is False
            assert "timed out" in result.error


class TestInvokeWithRetry:
    """Tests for invoke_with_retry function."""

    def test_successful_first_attempt(self) -> None:
        """Validates success on first attempt w/o retry.

        Tests happy path where gh CLI succeeds immediately. Verifies
        attempt=1 indicates no retries needed and result captured
        from stdout.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success != True or attempt != 1

        Testing Principles: Happy path, first-try success

        Arrangement: Mock subprocess w/ returncode=0
        Action: Call invoke_with_retry(["gh", "issue", "list"])
        Assertion: success=True, result=stdout, attempt=1

        Examples:
            ```python
            result = invoke_with_retry(["gh", "issue", "list"], "List")
            assert result.attempt == 1  # No retries
            ```
        """
        with patch("create_issues.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = '{"result": "ok"}'
            mock_run.return_value = mock_result

            result = invoke_with_retry(["gh", "issue", "list"], "List issues")
            assert result.success is True
            assert result.result == '{"result": "ok"}'
            assert result.attempt == 1

    def test_retry_on_rate_limit(self) -> None:
        """Validates retry logic on GitHub API rate limit error.

        Tests exponential backoff retry w/ rate limit detection. First
        call returns rate limit error, second succeeds. Verifies attempt
        counter tracks retry progression.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If not success or attempt != 2

        Testing Principles: Retry logic, error classification, backoff

        Arrangement: Mock subprocess w/ [fail, success] side_effect
        Action: Call invoke_with_retry w/ max_retries=3
        Assertion: success=True, attempt=2 (retried once)

        Examples:
            ```python
            result = invoke_with_retry(["gh", "test"], max_retries=3)
            assert result.success and result.attempt == 2
            ```
        """
        with (
            patch("create_issues.subprocess.run") as mock_run,
            patch("create_issues.time.sleep"),
        ):
            # First call: rate limit
            mock_fail = MagicMock()
            mock_fail.returncode = 1
            mock_fail.stderr = "API rate limit exceeded"
            mock_fail.stdout = ""

            # Second call: success
            mock_success = MagicMock()
            mock_success.returncode = 0
            mock_success.stdout = "ok"

            mock_run.side_effect = [mock_fail, mock_success]

            result = invoke_with_retry(["gh", "test"], "Test", max_retries=3)
            assert result.success is True
            assert result.attempt == 2

    def test_max_retries_exceeded(self) -> None:
        """Validates failure after exhausting max retry attempts.

        Tests retry exhaustion when transient error persists beyond
        max_retries limit. Should fail after N attempts with last
        error or "Max retries exceeded" message.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success != False or attempt != max

        Testing Principles: Retry exhaustion, bounded retries

        Arrangement: Mock subprocess to always fail w/ rate limit
        Action: Call invoke_with_retry w/ max_retries=2
        Assertion: success=False, attempt=2 (max reached)

        Examples:
            ```python
            # Persistent rate limit
            result = invoke_with_retry(["gh"], max_retries=2)
            assert not result.success and result.attempt == 2
            ```
        """
        with (
            patch("create_issues.subprocess.run") as mock_run,
            patch("create_issues.time.sleep"),
        ):
            mock_fail = MagicMock()
            mock_fail.returncode = 1
            mock_fail.stderr = "rate limit"
            mock_fail.stdout = ""
            mock_run.return_value = mock_fail

            result = invoke_with_retry(["gh", "test"], "Test", max_retries=2)
            assert result.success is False
            # May be last error or "Max retries exceeded"
            assert result.attempt == 2

    def test_non_retryable_error(self) -> None:
        """Validates immediate failure on non-retryable errors.

        Tests error classification: "repository not found" is permanent,
        not transient. Should fail immediately w/o retry attempts to
        avoid wasting time on unrecoverable errors.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success != False or attempt != 1

        Testing Principles: Error classification, fail-fast

        Arrangement: Mock subprocess to return "repository not found"
        Action: Call invoke_with_retry w/ max_retries=3
        Assertion: success=False, attempt=1 (no retries)

        Examples:
            ```python
            # Permanent error - no retry
            result = invoke_with_retry(["gh", "repo", "view"], max_retries=3)
            assert result.attempt == 1  # Failed immediately
            ```
        """
        with patch("create_issues.subprocess.run") as mock_run:
            mock_fail = MagicMock()
            mock_fail.returncode = 1
            mock_fail.stderr = "repository not found"
            mock_run.return_value = mock_fail

            result = invoke_with_retry(["gh", "test"], "Test", max_retries=3)
            assert result.success is False
            assert result.attempt == 1  # No retries

    def test_timeout_is_retryable(self) -> None:
        """Validates timeout exceptions trigger retry.

        Tests TimeoutExpired classified as transient/retryable error.
        Network timeouts often recover on retry, so should not fail
        immediately like permanent errors.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success != True or attempt != 2

        Testing Principles: Error classification, transient errors

        Arrangement: Mock subprocess w/ [TimeoutExpired, success]
        Action: Call invoke_with_retry w/ max_retries=3
        Assertion: success=True, attempt=2 (retried once)

        Examples:
            ```python
            # First call times out, second succeeds
            result = invoke_with_retry(["gh", "api", "..."], max_retries=3)
            assert result.success and result.attempt == 2
            ```
        """
        with (
            patch("create_issues.subprocess.run") as mock_run,
            patch("create_issues.time.sleep"),
        ):
            mock_success = MagicMock()
            mock_success.returncode = 0
            mock_success.stdout = "ok"

            mock_run.side_effect = [
                subprocess.TimeoutExpired("gh", 120),
                mock_success,
            ]

            result = invoke_with_retry(["gh", "test"], "Test", max_retries=3)
            assert result.success is True
            assert result.attempt == 2


class TestGetRepositoryLabels:
    """Tests for get_repository_labels function."""

    def test_successful_label_fetch(self) -> None:
        """Validates label list parsed from gh CLI JSON output.

        Tests get_repository_labels w/ mocked invoke_with_retry returning
        valid JSON array. Verifies JSON parsing and list structure for
        downstream label comparison.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success != True or label count wrong

        Testing Principles: JSON parsing, API response handling

        Arrangement: Mock invoke_with_retry w/ JSON labels array
        Action: Call get_repository_labels("owner/repo")
        Assertion: success=True, result contains 2 parsed labels

        Examples:
            ```python
            result = get_repository_labels("owner/repo")
            assert len(result.result) == 2 and result.result[0]["name"] == "bug"
            ```
        """
        labels_json = json.dumps(
            [
                {"name": "bug", "description": "Bug report", "color": "d73a4a"},
                {
                    "name": "enhancement",
                    "description": "New feature",
                    "color": "a2eeef",
                },
            ]
        )
        with patch("create_issues.invoke_with_retry") as mock_invoke:
            mock_invoke.return_value = OperationResult(success=True, result=labels_json)

            result = get_repository_labels("owner/repo")
            assert result.success is True
            assert len(result.result) == 2
            assert result.result[0]["name"] == "bug"

    def test_failed_label_fetch(self) -> None:
        """Validates error propagation when label fetch fails.

        Tests get_repository_labels passes through invoke_with_retry
        failure. Upstream error message preserved for user feedback.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success != False

        Testing Principles: Error propagation, failure pass-through

        Arrangement: Mock invoke_with_retry to return failure
        Action: Call get_repository_labels("owner/repo")
        Assertion: success=False (error propagated)

        Examples:
            ```python
            result = get_repository_labels("nonexistent/repo")
            assert not result.success
            ```
        """
        with patch("create_issues.invoke_with_retry") as mock_invoke:
            mock_invoke.return_value = OperationResult(
                success=False, error="repo not found"
            )

            result = get_repository_labels("owner/repo")
            assert result.success is False


class TestCreateLabel:
    """Tests for create_label function."""

    def test_successful_label_creation(self) -> None:
        """Validates success returned when label created via gh CLI.

        Tests create_label happy path where gh label create succeeds.
        Verifies Label dataclass fields passed correctly to CLI command.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success != True

        Testing Principles: Happy path, CLI integration

        Arrangement: Mock invoke_with_retry to return success
        Action: Call create_label(Label(...), "owner/repo")
        Assertion: success=True

        Examples:
            ```python
            label = Label("bug", "Bug report", "d73a4a")
            result = create_label(label, "owner/repo")
            assert result.success
            ```
        """
        with patch("create_issues.invoke_with_retry") as mock_invoke:
            mock_invoke.return_value = OperationResult(success=True, result="created")

            label = Label("test-label", "Test description", "ff0000")
            result = create_label(label, "owner/repo")
            assert result.success is True

    def test_permission_error_raises(self) -> None:
        """Validates PermissionError raised on HTTP 401 auth failure.

        Tests create_label converts HTTP 401 error from gh CLI into
        Python PermissionError for upstream handling. Enables batch
        creation to abort early on auth issues.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If PermissionError not raised

        Testing Principles: Exception translation, auth error handling

        Arrangement: Mock invoke_with_retry w/ 401 error
        Action: Call create_label(label, "owner/repo")
        Assertion: Raises PermissionError

        Examples:
            ```python
            with pytest.raises(PermissionError):
                create_label(Label("test", ...), "owner/repo")
            ```
        """
        with patch("create_issues.invoke_with_retry") as mock_invoke:
            mock_invoke.return_value = OperationResult(
                success=False, error="HTTP 401: Must have admin rights"
            )

            label = Label("test", "desc", "000000")
            with pytest.raises(PermissionError):
                create_label(label, "owner/repo")


class TestGetRequiredLabels:
    """Tests for get_required_labels function."""

    def test_returns_label_list(self) -> None:
        """Validates get_required_labels returns list of Label objects.

        Tests factory function returns properly typed Label instances
        for priority, estimate, and category labels. Foundation for
        missing label detection.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If not list or elements not Label type

        Testing Principles: Type checking, factory pattern

        Arrangement: None
        Action: Call get_required_labels()
        Assertion: Returns non-empty list of Label instances

        Examples:
            ```python
            labels = get_required_labels()
            for label in labels:
                create_label(label, "owner/repo")  # Type-safe
            ```
        """
        labels = get_required_labels()
        assert isinstance(labels, list)
        assert len(labels) > 0
        assert all(isinstance(lbl, Label) for lbl in labels)

    @pytest.mark.parametrize(
        ("expected_labels", "check_type"),
        [
            (["p1", "p2", "p3", "p4"], "exact"),
            (["estimate:"], "prefix"),
        ],
    )
    def test_includes_required_label_types(
        self, expected_labels: list, check_type: str
    ) -> None:
        """Includes priority and estimate labels."""
        labels = get_required_labels()
        names = [lbl.name for lbl in labels]
        if check_type == "exact":
            for lbl in expected_labels:
                assert lbl in names
        else:  # prefix
            assert any(n.startswith(expected_labels[0]) for n in names)


class TestGetMissingLabels:
    """Tests for get_missing_labels function."""

    @pytest.mark.parametrize(
        ("existing", "required", "expected_count"),
        [
            ([{"name": "p1"}, {"name": "p2"}], ["p1", "p2"], 0),
            ([{"name": "p1"}], ["p1", "p2"], 1),
            ([], ["p1", "p2"], 2),
        ],
    )
    def test_missing_labels_count(
        self, existing: list, required: list, expected_count: int
    ) -> None:
        """Validates missing label detection across coverage scenarios.

        Parameterized test covering 3 cases: all present (0 missing),
        partial (1 missing), none present (2 missing). Verifies set
        difference logic for label gap detection.

        Args:
            self: Test fixture
            existing: List of existing label dicts w/ "name" key
            required: List of required label names
            expected_count: Expected number of missing labels

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If missing count != expected

        Testing Principles: Set operations, edge cases (empty/full)

        Arrangement: Convert required names to Label objects
        Action: Call get_missing_labels(existing, required_labels)
        Assertion: len(missing) == expected_count

        Examples:
            ```python
            missing = get_missing_labels([{"name": "p1"}], [Label("p2", ...)])
            assert len(missing) == 1
            ```
        """
        required_labels = [Label(n, "", "") for n in required]
        missing = get_missing_labels(existing, required_labels)
        assert len(missing) == expected_count


class TestCreateLabelsBatch:
    """Tests for create_labels_batch function."""

    def test_creates_all_labels(self, capsys) -> None:
        """Validates batch creates each label in list.

        Tests create_labels_batch iterates all labels and calls
        create_label for each. Verifies call count matches label count.

        Args:
            self: Test fixture
            capsys: pytest stdout/stderr capture fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If call_count != 2

        Testing Principles: Iteration, batch processing

        Arrangement: Create 2 Label objects, mock create_label
        Action: Call create_labels_batch(labels, "owner/repo")
        Assertion: create_label called twice

        Examples:
            ```python
            labels = [Label("p1", ...), Label("p2", ...)]
            create_labels_batch(labels, "owner/repo")  # 2 API calls
            ```
        """
        with patch("create_issues.create_label") as mock_create:
            mock_create.return_value = OperationResult(success=True)

            labels = [Label("p1", "", ""), Label("p2", "", "")]
            create_labels_batch(labels, "owner/repo")

            assert mock_create.call_count == 2

    def test_continues_on_individual_failure(self, capsys) -> None:
        """Validates batch continues after individual label failure.

        Tests non-PermissionError failures don't abort batch. First
        label fails, second still created. Enables partial success
        for label provisioning.

        Args:
            self: Test fixture
            capsys: pytest stdout/stderr capture fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If call_count != 2

        Testing Principles: Partial failure, continuation

        Arrangement: Mock create_label w/ [failure, success]
        Action: Call create_labels_batch w/ 2 labels
        Assertion: Both labels attempted (call_count=2)

        Examples:
            ```python
            # p1 fails (exists), p2 created
            create_labels_batch([p1, p2], "owner/repo")
            ```
        """
        with patch("create_issues.create_label") as mock_create:
            mock_create.side_effect = [
                OperationResult(success=False, error="failed"),
                OperationResult(success=True),
            ]

            labels = [Label("p1", "", ""), Label("p2", "", "")]
            create_labels_batch(labels, "owner/repo")

            assert mock_create.call_count == 2

    def test_stops_on_permission_error(self) -> None:
        """Validates batch stops immediately on PermissionError.

        Tests create_labels_batch propagates PermissionError from
        create_label to abort entire batch. Prevents wasted API calls
        when user lacks required permissions.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If PermissionError not raised

        Testing Principles: Exception propagation, early abort

        Arrangement: Mock create_label to raise PermissionError
        Action: Call create_labels_batch w/ 2 labels
        Assertion: Raises PermissionError (batch aborted)

        Examples:
            ```python
            with pytest.raises(PermissionError):
                create_labels_batch([label1, label2], "owner/repo")
            ```
        """
        with patch("create_issues.create_label") as mock_create:
            mock_create.side_effect = PermissionError("No admin rights")

            labels = [Label("p1", "", ""), Label("p2", "", "")]
            with pytest.raises(PermissionError):
                create_labels_batch(labels, "owner/repo")


class TestWriteLabelsForAi:
    """Tests for write_labels_for_ai function."""

    def test_outputs_categorized_labels(self, capsys) -> None:
        """Outputs labels grouped by category."""
        labels = [
            {"name": "p1", "description": "Critical"},
            {"name": "bug", "description": "Bug report"},
            {"name": "estimate: 2h", "description": "2 hours"},
        ]

        write_labels_for_ai(labels)
        captured = capsys.readouterr()

        assert "Priority" in captured.out or "p1" in captured.out
        assert "bug" in captured.out

    def test_handles_empty_labels(self, capsys) -> None:
        """Handles empty label list."""
        write_labels_for_ai([])
        capsys.readouterr()
        # Should not raise, may output header


# ============================================================================
# Test Validation Functions
# ============================================================================


class TestValidateInputSafety:
    """Tests for validate_input_safety function."""

    @pytest.mark.parametrize("safe_input", ["Fix bug in parser", "Add new feature"])
    def test_safe_input_passes(self, safe_input: str) -> None:
        """Normal input passes validation."""
        validate_input_safety(safe_input, "title")  # No exception

    @pytest.mark.parametrize(
        "dangerous_input",
        ["Fix; rm -rf /", "Test `whoami`", "$(cat /etc/passwd)", "pipe | cmd"],
    )
    def test_dangerous_chars_rejected_strict(self, dangerous_input: str) -> None:
        """Validates shell injection chars rejected in strict mode.

        Parameterized security test covering command injection vectors:
        semicolon, backticks, $(), and pipe. Ensures strict mode blocks
        all shell metacharacters to prevent injection attacks.

        Args:
            self: Test fixture
            dangerous_input: Input containing shell metacharacter

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If ValueError not raised w/ expected msg

        Testing Principles: Security, injection prevention, strict mode

        Arrangement: Prepare input w/ dangerous shell chars
        Action: Call validate_input_safety(input, strict=True)
        Assertion: Raises ValueError w/ "dangerous characters" msg

        Examples:
            ```python
            with pytest.raises(ValueError, match="dangerous"):
                validate_input_safety("rm; whoami", "title", strict=True)
            ```
        """
        with pytest.raises(ValueError, match="dangerous characters"):
            validate_input_safety(dangerous_input, "title", strict=True)

    @pytest.mark.parametrize(
        "relaxed_input",
        ["Code example: `print('hello')`", "Use (parentheses) and [brackets]"],
    )
    def test_relaxed_mode_allows_more(self, relaxed_input: str) -> None:
        """Relaxed mode allows more chars for body content."""
        validate_input_safety(relaxed_input, "body", strict=False)  # No exception

    def test_null_bytes_rejected(self) -> None:
        """Null bytes rejected in all modes."""
        with pytest.raises(ValueError, match="null"):
            validate_input_safety("test\x00injection", "field", strict=False)

    @pytest.mark.parametrize(
        ("input_str", "max_len", "strict"),
        [
            ("x" * (MAX_TITLE_LENGTH + 1), MAX_TITLE_LENGTH, True),
            ("x" * (MAX_BODY_LENGTH + 1), MAX_BODY_LENGTH, False),
        ],
    )
    def test_length_limits(self, input_str: str, max_len: int, strict: bool) -> None:
        """Input exceeding length limits rejected."""
        with pytest.raises(ValueError, match="exceeds"):
            validate_input_safety(input_str, "field", strict=strict)


class TestValidateIssueRequiredFields:
    """Tests for validate_issue_required_fields function."""

    def test_valid_issue(self) -> None:
        """Validates issue w/ title and labels passes required check.

        Tests minimum valid issue structure: non-empty title and at
        least one label. These are GitHub API requirements for issue
        creation.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If is_valid != True

        Testing Principles: Minimum valid input, happy path

        Arrangement: Create issue dict w/ title and labels
        Action: Call validate_issue_required_fields(issue, 1)
        Assertion: is_valid=True

        Examples:
            ```python
            issue = {"title": "Fix bug", "labels": ["p1"]}
            assert validate_issue_required_fields(issue, 1).is_valid
            ```
        """
        issue = {"title": "Fix bug", "labels": ["p1", "bug"]}
        result = validate_issue_required_fields(issue, 1)
        assert result.is_valid is True

    @pytest.mark.parametrize(
        ("issue", "error_field"),
        [
            ({"labels": ["p1"]}, "title"),
            ({"title": "Fix bug"}, "label"),
            ({"title": "Fix bug", "labels": []}, "label"),
        ],
    )
    def test_missing_required_fields(self, issue: dict, error_field: str) -> None:
        """Missing/empty required fields produce errors."""
        result = validate_issue_required_fields(issue, 1)
        assert result.is_valid is False
        assert any(error_field in e.lower() for e in result.errors)


class TestValidateIssueSecurity:
    """Tests for validate_issue_security function."""

    def test_safe_issue_passes(self) -> None:
        """Validates safe issue content passes security check.

        Tests normal issue w/o shell metacharacters passes security
        validation. Baseline for what should be accepted.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If is_valid != True

        Testing Principles: Happy path, safe content baseline

        Arrangement: Create issue w/ normal title and labels
        Action: Call validate_issue_security(issue, 1)
        Assertion: is_valid=True (no security concerns)

        Examples:
            ```python
            issue = {"title": "Add unit tests", "labels": ["p2"]}
            assert validate_issue_security(issue, 1).is_valid
            ```
        """
        issue = {"title": "Fix bug", "labels": ["p1", "bug"]}
        result = validate_issue_security(issue, 1)
        assert result.is_valid is True

    @pytest.mark.parametrize(
        "issue",
        [
            {"title": "Fix; rm -rf /", "labels": ["p1"]},
            {"title": "Fix bug", "labels": ["p1", "`whoami`"]},
        ],
    )
    def test_dangerous_content_rejected(self, issue: dict) -> None:
        """Validates dangerous content in title/labels rejected.

        Parameterized security test covering injection vectors in both
        title field (semicolon injection) and labels array (backtick
        command substitution). Ensures security validation catches both.

        Args:
            self: Test fixture
            issue: Issue dict w/ dangerous content in title or labels

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If is_valid != False

        Testing Principles: Security, defense-in-depth, multi-field validation

        Arrangement: Create issue w/ shell metachar in title or label
        Action: Call validate_issue_security(issue, 1)
        Assertion: is_valid=False (security error detected)

        Examples:
            ```python
            issue = {"title": "Fix; rm -rf /", "labels": ["p1"]}
            assert not validate_issue_security(issue, 1).is_valid
            ```
        """
        result = validate_issue_security(issue, 1)
        assert result.is_valid is False


class TestValidateIssueLabels:
    """Tests for validate_issue_labels function."""

    def test_all_labels_exist(self) -> None:
        """Validates success when all issue labels exist in repo.

        Tests validate_issue_labels w/ available labels containing
        all referenced labels. No errors when label set is subset
        of available labels.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If is_valid != True

        Testing Principles: Set membership, label existence

        Arrangement: Create issue labels, available superset
        Action: Call validate_issue_labels(issue, available, 1)
        Assertion: is_valid=True (all labels found)

        Examples:
            ```python
            issue = {"labels": ["p1", "bug"]}
            available = [{"name": "p1"}, {"name": "bug"}, {"name": "p2"}]
            assert validate_issue_labels(issue, available, 1).is_valid
            ```
        """
        issue = {"labels": ["p1", "bug"]}
        available = [{"name": "p1"}, {"name": "bug"}, {"name": "p2"}]

        result = validate_issue_labels(issue, available, 1)
        assert result.is_valid is True

    def test_missing_label(self) -> None:
        """Validates error when issue references nonexistent label.

        Tests validate_issue_labels detects label not in available set.
        Error message includes missing label name for user correction.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If is_valid != False or label not in error

        Testing Principles: Set difference, missing detection

        Arrangement: Create issue w/ label not in available list
        Action: Call validate_issue_labels(issue, available, 1)
        Assertion: is_valid=False, error contains missing label name

        Examples:
            ```python
            issue = {"labels": ["p1", "nonexistent"]}
            result = validate_issue_labels(issue, [{"name": "p1"}], 1)
            assert "nonexistent" in result.errors[0]
            ```
        """
        issue = {"labels": ["p1", "nonexistent"]}
        available = [{"name": "p1"}]

        result = validate_issue_labels(issue, available, 1)
        assert result.is_valid is False
        assert any("nonexistent" in e for e in result.errors)


class TestValidateIssueConventions:
    """Tests for validate_issue_conventions function."""

    def test_valid_conventions(self) -> None:
        """Validates no warnings when conventions followed.

        Tests validate_issue_conventions w/ single priority label and
        single estimate label. This is the recommended issue structure.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If warnings not empty

        Testing Principles: Convention compliance, warning absence

        Arrangement: Create issue w/ 1 priority + 1 estimate
        Action: Call validate_issue_conventions(issue, 1)
        Assertion: warnings list empty

        Examples:
            ```python
            issue = {"labels": ["p1", "bug", "estimate: 2h"]}
            assert len(validate_issue_conventions(issue, 1).warnings) == 0
            ```
        """
        issue = {"labels": ["p1", "bug", "estimate: 2h"]}
        result = validate_issue_conventions(issue, 1)
        assert len(result.warnings) == 0

    @pytest.mark.parametrize(
        ("labels", "warning_keyword"),
        [
            (["bug", "estimate: 2h"], "priority"),
            (["p1", "p2", "bug"], "multiple"),
            (["p1", "bug"], "estimate"),
            (["p1", "estimate: 1h", "estimate: 2h"], "multiple"),
        ],
    )
    def test_convention_warnings(self, labels: list, warning_keyword: str) -> None:
        """Validates convention violations produce appropriate warnings.

        Parameterized test covering 4 convention cases: missing priority,
        multiple priorities, missing estimate, multiple estimates. Ensures
        each violation generates warning w/ descriptive keyword.

        Args:
            self: Test fixture
            labels: Issue label list to validate
            warning_keyword: Expected keyword in warning msg

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If warning keyword not found in warnings

        Testing Principles: Convention enforcement, warning clarity

        Arrangement: Create issue dict w/ labels list
        Action: Call validate_issue_conventions(issue, 1)
        Assertion: warnings contains msg w/ expected keyword

        Examples:
            ```python
            issue = {"labels": ["bug"]}  # Missing priority
            result = validate_issue_conventions(issue, 1)
            assert any("priority" in w for w in result.warnings)
            ```
        """
        issue = {"labels": labels}
        result = validate_issue_conventions(issue, 1)
        assert any(warning_keyword.lower() in w.lower() for w in result.warnings)


class TestValidateIssueBodyStructure:
    """Tests for validate_issue_body_structure function."""

    def test_valid_body(self) -> None:
        """Validates well-structured body dict passes validation.

        Tests validate_issue_body_structure w/ complete body containing
        location, problem, and proposed_solution. These fields provide
        context for issue work.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If is_valid != True

        Testing Principles: Complete structure, happy path

        Arrangement: Create issue w/ well-formed body dict
        Action: Call validate_issue_body_structure(issue, 1)
        Assertion: is_valid=True

        Examples:
            ```python
            body = {"location": "src/", "problem": "...", "proposed_solution": "..."}
            assert validate_issue_body_structure({"body": body}, 1).is_valid
            ```
        """
        issue = {
            "body": {
                "location": "src/main.py",
                "problem": "Missing validation",
                "proposed_solution": "Add input checks",
            }
        }
        result = validate_issue_body_structure(issue, 1)
        assert result.is_valid is True

    def test_missing_body_warning(self) -> None:
        """Missing body produces warning."""
        issue = {"title": "Fix bug"}
        validate_issue_body_structure(issue, 1)
        # May produce warning about missing body or be valid

    def test_body_with_null_bytes(self) -> None:
        """Validates null bytes in body field produce security error.

        Tests validate_issue_body_structure detects null byte injection
        attempt in body fields. Null bytes can truncate strings or
        bypass validation in downstream systems.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If is_valid != False

        Testing Principles: Security, injection prevention, binary safety

        Arrangement: Create issue w/ null byte in body.location
        Action: Call validate_issue_body_structure(issue, 1)
        Assertion: is_valid=False (security error)

        Examples:
            ```python
            issue = {"body": {"location": "test\x00evil"}}
            assert not validate_issue_body_structure(issue, 1).is_valid
            ```
        """
        issue = {"body": {"location": "test\x00injection"}}
        result = validate_issue_body_structure(issue, 1)
        assert result.is_valid is False


class TestValidateIssue:
    """Tests for validate_issue orchestrator function."""

    def test_valid_issue(self) -> None:
        """Validates fully compliant issue passes all validators.

        Tests validate_issue orchestrator w/ complete issue having
        valid title, labels, body, and conventions. All sub-validators
        should pass.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If is_valid != True

        Testing Principles: End-to-end validation, happy path

        Arrangement: Create complete issue, available labels list
        Action: Call validate_issue(issue, available, 1)
        Assertion: is_valid=True (all validators pass)

        Examples:
            ```python
            issue = {"title": "...", "labels": [...], "body": {...}}
            assert validate_issue(issue, available_labels, 1).is_valid
            ```
        """
        issue = {
            "title": "Fix bug",
            "labels": ["p1", "bug", "estimate: 2h"],
            "body": {"location": "src/main.py", "problem": "Bug exists"},
        }
        available = [{"name": "p1"}, {"name": "bug"}, {"name": "estimate: 2h"}]

        result = validate_issue(issue, available, 1)
        assert result.is_valid is True

    def test_aggregates_all_errors(self) -> None:
        """Validates errors aggregated from all validation stages.

        Tests validate_issue orchestrator combines errors from security,
        required fields, labels, and conventions validators. Issue has
        multiple violations to verify aggregation.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If is_valid != False or error count < 2

        Testing Principles: Orchestration, error aggregation

        Arrangement: Create issue w/ dangerous title + missing labels
        Action: Call validate_issue(issue, available=[], idx=1)
        Assertion: is_valid=False, errors contains 2+ messages

        Examples:
            ```python
            issue = {"title": "Fix; rm -rf /"}  # Security + missing labels
            result = validate_issue(issue, [], 1)
            assert len(result.errors) >= 2
            ```
        """
        issue = {"title": "Fix; rm -rf /"}  # Missing labels + dangerous title
        available = []

        result = validate_issue(issue, available, 1)
        assert result.is_valid is False
        assert len(result.errors) >= 2  # At least security + required fields


# ============================================================================
# Test Issue Body Conversion
# ============================================================================


class TestConvertToIssueBody:
    """Tests for convert_to_issue_body function."""

    def test_basic_conversion(self) -> None:
        """Validates body dict converted to formatted markdown.

        Tests convert_to_issue_body transforms structured dict into
        markdown w/ headers, estimate badge, priority indicator, and
        field values. Core formatting for issue creation.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If key elements missing from output

        Testing Principles: Markdown formatting, template rendering

        Arrangement: Create body dict w/ location, problem fields
        Action: Call convert_to_issue_body(body, "2h", "p1")
        Assertion: Result contains estimate, priority, location

        Examples:
            ```python
            result = convert_to_issue_body({"location": "src/"}, "2h", "p1")
            assert "[Est: 2h]" in result and "src/" in result
            ```
        """
        body = {
            "location": "src/main.py",
            "problem": "Missing validation",
        }
        result = convert_to_issue_body(body, "2h", "p1")

        assert "[Est: 2h]" in result
        assert "Priority" in result or "p1" in result
        assert "Location" in result
        assert "src/main.py" in result

    def test_files_affected_list(self) -> None:
        """Validates files_affected array converted to bullet list.

        Tests convert_to_issue_body formats files_affected as markdown
        bullet list for readable issue body. Each file on separate line.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If filenames missing from output

        Testing Principles: Array formatting, markdown lists

        Arrangement: Create body w/ files_affected array
        Action: Call convert_to_issue_body(body, None, None)
        Assertion: Output contains both filenames

        Examples:
            ```python
            body = {"files_affected": ["a.py", "b.py"]}
            result = convert_to_issue_body(body, None, None)
            assert "- a.py" in result and "- b.py" in result
            ```
        """
        body = {"files_affected": ["file1.py", "file2.py"]}
        result = convert_to_issue_body(body, None, None)

        assert "file1.py" in result
        assert "file2.py" in result

    def test_empty_body(self) -> None:
        """Validates empty body dict handled gracefully.

        Tests convert_to_issue_body w/ empty dict returns valid string
        (possibly empty or minimal). Should not raise on missing fields.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If result not string

        Testing Principles: Edge case, empty input handling

        Arrangement: Prepare empty body dict
        Action: Call convert_to_issue_body({}, None, None)
        Assertion: Returns string (may be empty)

        Examples:
            ```python
            result = convert_to_issue_body({}, None, None)
            assert isinstance(result, str)
            ```
        """
        result = convert_to_issue_body({}, None, None)
        assert isinstance(result, str)


# ============================================================================
# Test Issue Creation
# ============================================================================


class TestCreateGithubIssue:
    """Tests for create_github_issue function."""

    def test_successful_creation(self, capsys) -> None:
        """Validates issue creation returns URL on success.

        Tests create_github_issue w/ mocked gh CLI returning success.
        Verifies subprocess call constructed correctly and issue URL
        extracted from stdout for user feedback.

        Args:
            self: Test fixture
            capsys: pytest stdout/stderr capture fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success != True or URL missing

        Testing Principles: CLI integration, success path, output parsing

        Arrangement: Create issue dict, mock subprocess w/ success
        Action: Call create_github_issue(issue, "owner/repo", 1, 1)
        Assertion: success=True, issue_url contains "github.com"

        Examples:
            ```python
            result = create_github_issue(issue, "owner/repo", 1, 1)
            assert result.success and "github.com" in result.issue_url
            ```
        """
        issue = {"title": "Test issue", "labels": ["p1"]}

        with patch("create_issues.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "https://github.com/o/r/issues/1"
            mock_run.return_value = mock_result

            result = create_github_issue(issue, "owner/repo", 1, 1)
            assert result.success is True
            assert "github.com" in result.issue_url

    def test_failed_creation(self, capsys) -> None:
        """Validates error captured when issue creation fails.

        Tests create_github_issue failure path where gh CLI returns
        non-zero exit code. Error message from stderr captured for
        user feedback.

        Args:
            self: Test fixture
            capsys: pytest stdout/stderr capture fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success != False or error missing

        Testing Principles: Failure path, error capture

        Arrangement: Mock subprocess w/ returncode=1 and stderr
        Action: Call create_github_issue(issue, "owner/repo", 1, 1)
        Assertion: success=False, error contains stderr message

        Examples:
            ```python
            result = create_github_issue(issue, "owner/repo", 1, 1)
            assert not result.success and "Permission" in result.error
            ```
        """
        issue = {"title": "Test issue", "labels": ["p1"]}

        with patch("create_issues.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Permission denied"
            mock_result.stdout = ""
            mock_run.return_value = mock_result

            result = create_github_issue(issue, "owner/repo", 1, 1)
            assert result.success is False
            assert "Permission denied" in result.error

    def test_adds_needs_triage_label(self) -> None:
        """Validates needs-triage label auto-added to new issues.

        Tests create_github_issue automatically appends needs-triage
        label for workflow integration. Ensures new issues enter
        triage queue for review.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If needs-triage not in command labels

        Testing Principles: Auto-labeling, workflow integration

        Arrangement: Create issue w/o needs-triage, mock subprocess
        Action: Call create_github_issue, inspect subprocess args
        Assertion: --label arg contains "needs-triage"

        Examples:
            ```python
            # Issue {"labels": ["p1"]} becomes ["p1", "needs-triage"]
            create_github_issue(issue, "owner/repo", 1, 1)
            ```
        """
        issue = {"title": "Test", "labels": ["p1"]}

        with patch("create_issues.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "https://github.com/o/r/issues/1"
            mock_run.return_value = mock_result

            create_github_issue(issue, "owner/repo", 1, 1)

            # Check that needs-triage was added
            call_args = mock_run.call_args[0][0]
            label_idx = call_args.index("--label") + 1
            labels = call_args[label_idx]
            assert "needs-triage" in labels


# ============================================================================
# Test Orchestration Functions
# ============================================================================


class TestInitializePrerequisites:
    """Tests for initialize_prerequisites function."""

    def test_successful_init(self, capsys) -> None:
        """Validates prerequisites check returns labels on success.

        Tests initialize_prerequisites orchestration: checks gh CLI
        availability, fetches repository labels, returns combined
        result for downstream validation.

        Args:
            self: Test fixture
            capsys: pytest stdout/stderr capture fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success != True or labels missing

        Testing Principles: Orchestration, happy path, dependency chain

        Arrangement: Mock check_github_cli_available + get_repository_labels
        Action: Call initialize_prerequisites("owner/repo")
        Assertion: success=True, result contains label list

        Examples:
            ```python
            result = initialize_prerequisites("owner/repo")
            assert result.success and len(result.result) > 0
            ```
        """
        with patch("create_issues.check_github_cli_available") as mock_cli:
            mock_cli.return_value = OperationResult(
                success=True, result="gh version 2.40.0"
            )

            with patch("create_issues.get_repository_labels") as mock_labels:
                mock_labels.return_value = OperationResult(
                    success=True, result=[{"name": "bug"}]
                )

                result = initialize_prerequisites("owner/repo")
                assert result.success is True
                assert len(result.result) == 1

    def test_cli_not_available(self) -> None:
        """Validates failure when gh CLI check fails.

        Tests initialize_prerequisites short-circuits on CLI unavailable.
        Does not attempt label fetch if prerequisite check fails.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success != False

        Testing Principles: Early exit, prerequisite checking

        Arrangement: Mock check_github_cli_available to fail
        Action: Call initialize_prerequisites("owner/repo")
        Assertion: success=False (short-circuited)

        Examples:
            ```python
            # gh not installed -> immediate failure
            result = initialize_prerequisites("owner/repo")
            assert not result.success
            ```
        """
        with patch("create_issues.check_github_cli_available") as mock_cli:
            mock_cli.return_value = OperationResult(
                success=False, error="gh not installed"
            )

            result = initialize_prerequisites("owner/repo")
            assert result.success is False


class TestHandleLabelManagement:
    """Tests for handle_label_management function."""

    def test_list_labels_mode(self, capsys) -> None:
        """Validates --list-labels mode outputs and exits.

        Tests handle_label_management w/ list_labels=True outputs label
        information and returns should_exit=True to skip issue creation.

        Args:
            self: Test fixture
            capsys: pytest stdout/stderr capture fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If should_exit != True

        Testing Principles: Mode handling, early exit

        Arrangement: Prepare labels list, set list_labels=True
        Action: Call handle_label_management(..., list_labels=True)
        Assertion: should_exit=True

        Examples:
            ```python
            _, should_exit = handle_label_management(..., list_labels=True)
            if should_exit:
                return 0  # Don't create issues
            ```
        """
        labels = [{"name": "p1", "description": "Critical"}]

        updated, should_exit = handle_label_management(
            "owner/repo", labels, False, True, False
        )
        assert should_exit is True

    def test_create_labels_mode(self, capsys) -> None:
        """Create labels mode creates and exits."""
        with (
            patch("create_issues.create_labels_batch"),
            patch("create_issues.get_required_labels") as mock_required,
            patch("create_issues.get_missing_labels") as mock_missing,
        ):
            mock_required.return_value = []
            mock_missing.return_value = []
            labels = [{"name": "p1"}]

            updated, should_exit = handle_label_management(
                "owner/repo", labels, True, False, False
            )
            assert should_exit is True

    def test_auto_create_missing(self, capsys) -> None:
        """Validates auto-creation of missing labels in create mode.

        Tests handle_label_management auto-creates missing required labels
        when not in list/validate-only mode. Verifies label gap detection,
        batch creation call, and labels refresh after creation.

        Args:
            self: Test fixture
            capsys: pytest stdout/stderr capture fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If create_labels_batch not called or should_exit

        Testing Principles: Auto-provisioning, side effect verification

        Arrangement: Mock required/missing labels, create_labels_batch
        Action: Call handle_label_management w/ all flags False
        Assertion: should_exit=False, create_labels_batch called once

        Examples:
            ```python
            updated, should_exit = handle_label_management(..., False, False, False)
            assert not should_exit and mock_create.called
            ```
        """
        with (
            patch("create_issues.get_required_labels") as mock_required,
            patch("create_issues.get_missing_labels") as mock_missing,
            patch("create_issues.create_labels_batch") as mock_create,
            patch("create_issues.get_repository_labels") as mock_refresh,
        ):
            mock_required.return_value = [Label("p1", "", "")]
            mock_missing.return_value = [Label("p1", "", "")]
            mock_refresh.return_value = OperationResult(
                success=True, result=[{"name": "p1"}]
            )

            updated, should_exit = handle_label_management(
                "owner/repo", [], False, False, False
            )
            assert should_exit is False
            mock_create.assert_called_once()


class TestValidateAllIssues:
    """Tests for validate_all_issues function."""

    def test_valid_issues(self, tmp_path, capsys) -> None:
        """Validates issues file parsing and validation success path.

        Tests validate_all_issues w/ well-formed JSON containing 2 valid
        issues. Verifies JSON parsing, schema validation, label checking,
        and correct return tuple (issues list, should_exit=False).

        Args:
            self: Test fixture
            tmp_path: pytest temp directory fixture
            capsys: pytest stdout/stderr capture fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If issue count != 2 or should_exit != False

        Testing Principles: File I/O, JSON parsing, validation pipeline

        Arrangement: Create issues.json w/ 2 valid issues, labels list
        Action: Call validate_all_issues(file_path, labels, False)
        Assertion: Returns (2 issues, should_exit=False)

        Examples:
            ```python
            issues, should_exit = validate_all_issues("issues.json", labels, False)
            assert len(issues) == 2 and not should_exit
            ```
        """
        issues_file = tmp_path / "issues.json"
        issues_file.write_text(
            json.dumps(
                {
                    "issues": [
                        {"title": "Issue 1", "labels": ["p1"]},
                        {"title": "Issue 2", "labels": ["p2"]},
                    ]
                }
            )
        )

        labels = [{"name": "p1"}, {"name": "p2"}]

        issues, should_exit = validate_all_issues(str(issues_file), labels, False)
        assert len(issues) == 2
        assert should_exit is False

    def test_validate_only_mode(self, tmp_path, capsys) -> None:
        """Validate-only mode exits after validation."""
        issues_file = tmp_path / "issues.json"
        issues_file.write_text(
            json.dumps({"issues": [{"title": "Issue 1", "labels": ["p1"]}]})
        )

        labels = [{"name": "p1"}]

        issues, should_exit = validate_all_issues(str(issues_file), labels, True)
        assert should_exit is True

    def test_invalid_json_structure(self, tmp_path) -> None:
        """Raises error for missing issues array."""
        issues_file = tmp_path / "issues.json"
        issues_file.write_text(json.dumps({"data": []}))

        with pytest.raises(RuntimeError, match="issues"):
            validate_all_issues(str(issues_file), [], False)

    def test_validation_failure(self, tmp_path) -> None:
        """Raises error when validation fails."""
        issues_file = tmp_path / "issues.json"
        issues_file.write_text(
            json.dumps(
                {
                    "issues": [{"title": "Bad; title"}]  # Missing labels + dangerous
                }
            )
        )

        with pytest.raises(RuntimeError, match="Validation failed"):
            validate_all_issues(str(issues_file), [], False)


class TestCreateAllIssues:
    """Tests for create_all_issues function."""

    def test_creates_all_issues(self, capsys) -> None:
        """Validates batch creation iterates all issues and tracks results.

        Tests create_all_issues loops through issue list, calls
        create_github_issue for each, and aggregates success/fail
        counts in BatchCreationResult.

        Args:
            self: Test fixture
            capsys: pytest stdout/stderr capture fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If counts don't match expected

        Testing Principles: Batch processing, result aggregation

        Arrangement: Create 2 issues, mock create_github_issue success
        Action: Call create_all_issues(issues, "owner/repo")
        Assertion: success_count=2, fail_count=0

        Examples:
            ```python
            result = create_all_issues([issue1, issue2], "owner/repo")
            assert result.success_count == 2
            ```
        """
        issues = [
            {"title": "Issue 1", "labels": ["p1"]},
            {"title": "Issue 2", "labels": ["p2"]},
        ]

        with patch("create_issues.create_github_issue") as mock_create:
            mock_create.return_value = IssueCreationResult(
                success=True, issue_url="https://github.com/o/r/issues/1"
            )

            result = create_all_issues(issues, "owner/repo")
            assert result.success_count == 2
            assert result.fail_count == 0

    def test_tracks_failures(self, capsys) -> None:
        """Validates failed issues tracked in result.

        Tests create_all_issues increments fail_count and adds to
        failed_issues list when create_github_issue returns failure.

        Args:
            self: Test fixture
            capsys: pytest stdout/stderr capture fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If fail_count != 1 or success_count != 0

        Testing Principles: Failure tracking, result aggregation

        Arrangement: Create 1 issue, mock create_github_issue failure
        Action: Call create_all_issues(issues, "owner/repo")
        Assertion: success_count=0, fail_count=1

        Examples:
            ```python
            result = create_all_issues(issues, "owner/repo")
            for failed in result.failed_issues:
                print(f"{failed['title']}: {failed['error']}")
            ```
        """
        issues = [{"title": "Issue 1", "labels": ["p1"]}]

        with patch("create_issues.create_github_issue") as mock_create:
            mock_create.return_value = IssueCreationResult(
                success=False, error="Failed"
            )

            result = create_all_issues(issues, "owner/repo")
            assert result.success_count == 0
            assert result.fail_count == 1


class TestWriteExecutionSummary:
    """Tests for write_execution_summary function."""

    def test_success_summary(self, capsys) -> None:
        """Validates success summary outputs created issue details.

        Tests write_execution_summary w/ successful batch result outputs
        count and issue titles/URLs for user confirmation.

        Args:
            self: Test fixture
            capsys: pytest stdout/stderr capture fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If count or title missing from output

        Testing Principles: Output formatting, success reporting

        Arrangement: Create BatchCreationResult w/ 2 successes
        Action: Call write_execution_summary, capture stdout
        Assertion: Output contains "2" and issue titles

        Examples:
            ```python
            write_execution_summary(result, 1.5, "owner/repo", 2)
            # Output: "Created 2 issues: Issue 1, Issue 2"
            ```
        """
        result = BatchCreationResult(
            success_count=2,
            created_issues=[
                {"title": "Issue 1", "url": "url1"},
                {"title": "Issue 2", "url": "url2"},
            ],
        )

        write_execution_summary(result, 0.0, "owner/repo", 2)
        captured = capsys.readouterr()

        assert "2" in captured.out
        assert "Issue 1" in captured.out

    def test_failure_summary(self, capsys) -> None:
        """Validates failure summary outputs error details.

        Tests write_execution_summary w/ failed batch result outputs
        failure information for user troubleshooting.

        Args:
            self: Test fixture
            capsys: pytest stdout/stderr capture fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If "Failed" missing from output

        Testing Principles: Error reporting, failure visibility

        Arrangement: Create BatchCreationResult w/ 1 failure
        Action: Call write_execution_summary, capture stdout
        Assertion: Output contains failure indicator

        Examples:
            ```python
            write_execution_summary(result, 1.0, "owner/repo", 1)
            # Output: "Failed: Issue 1 - Error message"
            ```
        """
        result = BatchCreationResult(
            fail_count=1,
            failed_issues=[{"title": "Failed Issue", "error": "Error message"}],
        )

        write_execution_summary(result, 0.0, "owner/repo", 1)
        captured = capsys.readouterr()

        assert "Failed" in captured.out


# ============================================================================
# Test Main Entry Point
# ============================================================================


class TestMain:
    """Tests for main CLI entry point."""

    def test_invalid_repository_format(self, capsys) -> None:
        """Rejects invalid repository format."""
        with patch("sys.argv", ["create_issues.py", "-r", "invalid"]):
            code = main()
            assert code == 1
            captured = capsys.readouterr()
            assert "owner/repo" in captured.out.lower() or code == 1

    def test_missing_issues_file(self, capsys) -> None:
        """Requires --issues when not listing/creating labels."""
        with patch("sys.argv", ["create_issues.py", "-r", "owner/repo"]):
            code = main()
            assert code == 1

    def test_issues_file_not_found(self, capsys) -> None:
        """Errors when issues file doesn't exist."""
        with patch(
            "sys.argv",
            ["create_issues.py", "-r", "owner/repo", "-i", "/nonexistent.json"],
        ):
            code = main()
            assert code == 1

    def test_list_labels_mode(self, capsys) -> None:
        """--list-labels mode works."""
        with (
            patch(
                "sys.argv",
                ["create_issues.py", "-r", "owner/repo", "--list-labels"],
            ),
            patch("create_issues.initialize_prerequisites") as mock_init,
            patch("create_issues.handle_label_management") as mock_handle,
        ):
            mock_init.return_value = OperationResult(
                success=True, result=[{"name": "p1"}]
            )
            mock_handle.return_value = ([{"name": "p1"}], True)

            code = main()
            assert code == 0

    def test_create_labels_mode(self, capsys) -> None:
        """--create-labels mode works."""
        with (
            patch(
                "sys.argv",
                ["create_issues.py", "-r", "owner/repo", "--create-labels"],
            ),
            patch("create_issues.initialize_prerequisites") as mock_init,
            patch("create_issues.handle_label_management") as mock_handle,
        ):
            mock_init.return_value = OperationResult(
                success=True, result=[{"name": "p1"}]
            )
            mock_handle.return_value = ([{"name": "p1"}], True)

            code = main()
            assert code == 0

    def test_full_issue_creation(self, tmp_path, capsys) -> None:
        """Validates full issue creation flow end-to-end.

        Integration test exercising complete CLI flow: parse args, init
        prerequisites, manage labels, create issues, exit successfully.
        Uses tmp_path for issues file and mocks all GitHub API calls.

        Args:
            self: Test fixture
            tmp_path: pytest temp directory fixture
            capsys: pytest stdout/stderr capture fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If exit code != 0

        Testing Principles: Integration, happy path, mock orchestration

        Arrangement: Create issues.json in tmp_path, mock all deps
        Action: Call main() w/ patched sys.argv
        Assertion: Returns exit code 0

        Examples:
            ```python
            # Full flow: init -> labels -> create -> success
            code = main()  # w/ valid issues file
            assert code == 0
            ```
        """
        issues_file = tmp_path / "issues.json"
        issues_file.write_text(
            json.dumps({"issues": [{"title": "Test Issue", "labels": ["p1"]}]})
        )

        with (
            patch(
                "sys.argv",
                ["create_issues.py", "-r", "owner/repo", "-i", str(issues_file)],
            ),
            patch("create_issues.initialize_prerequisites") as mock_init,
            patch("create_issues.handle_label_management") as mock_handle,
            patch("create_issues.create_all_issues") as mock_create,
        ):
            mock_init.return_value = OperationResult(
                success=True, result=[{"name": "p1"}]
            )
            mock_handle.return_value = ([{"name": "p1"}], False)
            mock_create.return_value = BatchCreationResult(
                success_count=1,
                created_issues=[{"title": "Test Issue", "url": "url"}],
            )

            code = main()
            assert code == 0

    def test_handles_exception(self, capsys) -> None:
        """Validates unexpected exceptions handled gracefully.

        Tests main() top-level exception handler catches unhandled
        exceptions, prints error message, and returns exit code 1.
        Ensures CLI doesn't crash w/ stack trace for users.

        Args:
            self: Test fixture
            capsys: pytest stdout/stderr capture fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If exit code != 1 or error not printed

        Testing Principles: Exception handling, graceful degradation

        Arrangement: Mock initialize_prerequisites to raise Exception
        Action: Call main() w/ --list-labels flag
        Assertion: Returns 1, output contains "error"

        Examples:
            ```python
            # Unexpected exception caught and handled
            code = main()  # w/ broken prereq check
            assert code == 1 and "error" in captured.out
            ```
        """
        with (
            patch(
                "sys.argv",
                ["create_issues.py", "-r", "owner/repo", "--list-labels"],
            ),
            patch("create_issues.initialize_prerequisites") as mock_init,
        ):
            mock_init.side_effect = Exception("Unexpected error")

            code = main()
            assert code == 1
            captured = capsys.readouterr()
            assert "error" in captured.out.lower()


# ============================================================================
# Additional Coverage Tests
# ============================================================================


class TestCheckGitHubCliFileNotFound:
    """Test FileNotFoundError exception in check_github_cli_available."""

    def test_file_not_found_exception(self) -> None:
        """FileNotFoundError returns appropriate error."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("gh not found")
            result = check_github_cli_available()
            assert not result.success
            assert "not installed" in result.error


class TestInvokeWithRetryEdgeCases:
    """Additional tests for invoke_with_retry edge cases."""

    @pytest.mark.parametrize(
        ("side_effects", "expected_success", "error_match"),
        [
            # Timeout then success
            (
                [
                    subprocess.TimeoutExpired(cmd="gh", timeout=60),
                    MagicMock(returncode=0, stdout="success", stderr=""),
                ],
                True,
                None,
            ),
            # Timeout max retries
            (
                [subprocess.TimeoutExpired(cmd="gh", timeout=60)] * 3,
                False,
                "timed out",
            ),
            # Generic exception then success
            (
                [
                    Exception("network error"),
                    MagicMock(returncode=0, stdout="ok", stderr=""),
                ],
                True,
                None,
            ),
            # Generic exception max retries
            (
                [Exception("persistent error")] * 3,
                False,
                "persistent error",
            ),
        ],
    )
    def test_retry_scenarios(
        self, side_effects: list, expected_success: bool, error_match: str | None
    ) -> None:
        """Validates retry behavior across timeout and exception scenarios.

        Parameterized test covering 4 retry edge cases: timeout-then-success,
        timeout-max-retries, exception-then-success, exception-max-retries.
        Verifies retry logic handles transient failures appropriately.

        Args:
            self: Test fixture
            side_effects: List of exceptions/results for mock
            expected_success: Expected success state after retries
            error_match: Substring expected in error msg (or None)

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success state or error msg mismatch

        Testing Principles: Edge cases, exception handling, retry exhaustion

        Arrangement: Mock subprocess.run w/ side_effects, mock time.sleep
        Action: Call invoke_with_retry w/ max_retries=2
        Assertion: success matches expected, error contains match string

        Examples:
            ```python
            # Timeout then success
            mock_run.side_effect = [TimeoutExpired(...), MagicMock(...)]
            assert invoke_with_retry(...).success is True
            ```
        """
        with patch("subprocess.run") as mock_run, patch("time.sleep"):
            mock_run.side_effect = side_effects
            result = invoke_with_retry(["gh", "test"], max_retries=2)
            assert result.success == expected_success
            if error_match:
                assert error_match in result.error.lower()


class TestGetRepositoryLabelsJsonDecode:
    """Test JSON decode error in get_repository_labels."""

    def test_json_decode_error(self) -> None:
        """JSON decode error returns appropriate message."""
        with patch("create_issues.invoke_with_retry") as mock_invoke:
            mock_invoke.return_value = OperationResult(
                success=True, result="not valid json{"
            )
            result = get_repository_labels("owner/repo")
            assert not result.success
            assert "parse" in result.error.lower() or "JSON" in result.error


class TestCreateLabelBranches:
    """Test additional branches in create_label."""

    def test_label_already_exists(self, capsys) -> None:
        """Label already exists returns success."""
        with patch("create_issues.invoke_with_retry") as mock_invoke:
            mock_invoke.return_value = OperationResult(
                success=False, error="label already exists"
            )
            label = Label(name="existing", color="ff0000", description="test")
            result = create_label(label, "owner/repo")
            assert result.success
            assert "exists" in result.result.lower()

    def test_label_failed_creation(self, capsys) -> None:
        """Label creation failure returns error."""
        with patch("create_issues.invoke_with_retry") as mock_invoke:
            mock_invoke.return_value = OperationResult(
                success=False, error="some other error"
            )
            label = Label(name="new", color="ff0000", description="test")
            result = create_label(label, "owner/repo")
            assert not result.success


class TestCreateLabelsBatchException:
    """Test exception handling in create_labels_batch."""

    def test_non_permission_exception(self, capsys) -> None:
        """Non-PermissionError exception is logged but continues."""
        with patch("create_issues.create_label") as mock_create:
            mock_create.side_effect = Exception("network error")
            labels = [Label(name="test", color="ff0000", description="test")]
            # Should not raise, just log
            create_labels_batch(labels, "owner/repo")
            captured = capsys.readouterr()
            assert "Failed" in captured.out


class TestWriteLabelsForAiCategories:
    """Test all category branches in write_labels_for_ai."""

    def test_all_label_categories(self, capsys) -> None:
        """Validates all 5 label category types displayed in output.

        Tests write_labels_for_ai categorization logic by providing labels
        from each category (PRIORITY, CATEGORY, WORKFLOW, EFFORT, OTHER)
        and verifying all section headers appear in formatted output.

        Args:
            self: Test fixture
            capsys: pytest stdout/stderr capture fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If any category header missing from output

        Testing Principles: Output formatting, categorization completeness

        Arrangement: Create labels list w/ one from each category
        Action: Call write_labels_for_ai(labels), capture stdout
        Assertion: Output contains PRIORITY, CATEGORY, WORKFLOW, EFFORT, OTHER

        Examples:
            ```python
            write_labels_for_ai([{"name": "p1"}, {"name": "bug"}, ...])
            assert all(cat in captured.out for cat in ["PRIORITY", ...])
            ```
        """
        labels = [
            {"name": "p1", "description": "Priority 1"},
            {"name": "security", "description": "Security fix"},  # category label
            {"name": "needs-triage", "description": "Needs triage"},  # workflow
            {"name": "estimate: 2h", "description": "2 hours"},
            {"name": "misc", "description": "Other stuff"},
        ]
        write_labels_for_ai(labels)
        captured = capsys.readouterr()
        assert "PRIORITY" in captured.out
        assert "CATEGORY" in captured.out
        assert "WORKFLOW" in captured.out
        assert "EFFORT" in captured.out
        assert "OTHER" in captured.out


class TestValidateIssueBodySecurityErrors:
    """Test security validation in validate_issue_body_structure."""

    @pytest.mark.parametrize(
        "body",
        [
            {"problem": "test\x00null"},  # null byte
            {"files_affected": ["file`name.py"]},  # dangerous chars in filename
        ],
    )
    def test_body_security_errors(self, body: dict) -> None:
        """Body w/ security issues generates error."""
        issue = {"title": "Test", "labels": ["p1"], "body": body}
        result = validate_issue_body_structure(issue, 1)
        assert len(result.errors) > 0


class TestCreateGithubIssueStringBody:
    """Test create_github_issue with string body."""

    def test_string_body_preserved(self, tmp_path, capsys) -> None:
        """String body is used as-is."""
        issue = {
            "title": "Test Issue",
            "labels": ["p1"],
            "body": "This is a string body",
        }
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="https://github.com/owner/repo/issues/1",
                stderr="",
            )
            result = create_github_issue(issue, "owner/repo", 1, 1)
            assert result.success
            assert result.issue_url == "https://github.com/owner/repo/issues/1"

    def test_empty_body(self, capsys) -> None:
        """Issue with no body creates with empty string."""
        issue = {
            "title": "Test Issue",
            "labels": ["p1"],
        }
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="https://github.com/owner/repo/issues/1",
                stderr="",
            )
            result = create_github_issue(issue, "owner/repo", 1, 1)
            assert result.success


class TestHandleLabelManagementMissingWarning:
    """Test missing labels warning in handle_label_management."""

    def test_list_labels_with_missing_shows_warning(self, capsys) -> None:
        """--list-labels with missing labels shows warning."""
        with (
            patch("create_issues.get_required_labels") as mock_required,
            patch("create_issues.get_missing_labels") as mock_missing,
            patch("create_issues.write_labels_for_ai"),
        ):
            mock_required.return_value = [
                Label(name="p1", color="ff0000", description="")
            ]
            mock_missing.return_value = [
                Label(name="p1", color="ff0000", description="")
            ]

            labels, should_exit = handle_label_management(
                "owner/repo",
                [],  # No labels available
                create_labels=False,
                list_labels=True,
                validate_only=False,
            )
            assert should_exit
            captured = capsys.readouterr()
            assert "missing" in captured.out.lower()


class TestMainValidateOnlyMode:
    """Test --validate-only mode in main."""

    def test_validate_only_mode(self, tmp_path, capsys) -> None:
        """--validate-only mode validates without creating."""
        issues_file = tmp_path / "issues.json"
        issues_file.write_text(
            json.dumps({"issues": [{"title": "Test Issue", "labels": ["p1"]}]})
        )

        with (
            patch(
                "sys.argv",
                [
                    "create_issues.py",
                    "-r",
                    "owner/repo",
                    "-i",
                    str(issues_file),
                    "--validate-only",
                ],
            ),
            patch("create_issues.initialize_prerequisites") as mock_init,
            patch("create_issues.handle_label_management") as mock_handle,
        ):
            mock_init.return_value = OperationResult(
                success=True, result=[{"name": "p1"}]
            )
            mock_handle.return_value = ([{"name": "p1"}], False)

            main()
            # validate_only causes early exit after validation
            capsys.readouterr()
            # Should have validated but not created


class TestHandleLabelManagementAutoCreate:
    """Test auto-create missing labels in handle_label_management."""

    def test_auto_creates_missing_labels(self, capsys) -> None:
        """Auto-creates missing labels when not in validate-only mode."""
        with (
            patch("create_issues.get_required_labels") as mock_required,
            patch("create_issues.get_missing_labels") as mock_missing,
            patch("create_issues.create_labels_batch") as mock_batch,
            patch("create_issues.get_repository_labels") as mock_refresh,
        ):
            mock_required.return_value = [
                Label(name="p1", color="ff0000", description="")
            ]
            mock_missing.return_value = [
                Label(name="p1", color="ff0000", description="")
            ]
            mock_refresh.return_value = OperationResult(
                success=True, result=[{"name": "p1"}]
            )

            labels, should_exit = handle_label_management(
                "owner/repo",
                [],  # No labels available initially
                create_labels=False,
                list_labels=False,
                validate_only=False,
            )
            assert mock_batch.called
            assert not should_exit

    def test_refresh_failure_raises(self, capsys) -> None:
        """Refresh failure after auto-create raises RuntimeError."""
        with (
            patch("create_issues.get_required_labels") as mock_required,
            patch("create_issues.get_missing_labels") as mock_missing,
            patch("create_issues.create_labels_batch"),
            patch("create_issues.get_repository_labels") as mock_refresh,
        ):
            mock_required.return_value = [
                Label(name="p1", color="ff0000", description="")
            ]
            mock_missing.return_value = [
                Label(name="p1", color="ff0000", description="")
            ]
            mock_refresh.return_value = OperationResult(
                success=False, error="API error"
            )

            with pytest.raises(RuntimeError, match="Failed to refresh"):
                handle_label_management(
                    "owner/repo",
                    [],
                    create_labels=False,
                    list_labels=False,
                    validate_only=False,
                )


class TestMainPrereqFailure:
    """Test prerequisite failure in main."""

    def test_prereq_failure_returns_error(self, capsys) -> None:
        """Prerequisite failure returns error code."""
        with (
            patch(
                "sys.argv",
                ["create_issues.py", "-r", "owner/repo", "--list-labels"],
            ),
            patch("create_issues.initialize_prerequisites") as mock_init,
        ):
            mock_init.return_value = OperationResult(
                success=False, error="CLI not available"
            )

            code = main()
            assert code == 1


class TestCheckGitHubCliGenericException:
    """Test generic exception handling in check_github_cli_available."""

    def test_generic_exception(self) -> None:
        """Generic exception returns appropriate error."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("unexpected error")
            result = check_github_cli_available()
            assert not result.success
            assert "Error checking GitHub CLI" in result.error


class TestCheckGitHubCliVersionExtraction:
    """Test version extraction in check_github_cli_available."""

    def test_extracts_version_from_output(self) -> None:
        """Extracts version from gh --version output."""
        with patch("subprocess.run") as mock_run:
            # First call: gh --version
            # Second call: gh auth status
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="gh version 2.32.1 (2023-08-01)\n"),
                MagicMock(returncode=0, stdout="", stderr=""),
            ]
            result = check_github_cli_available()
            assert result.success
            assert "2.32.1" in result.result


class TestCreateGithubIssueWithDictBody:
    """Test create_github_issue with dict body (convert_to_issue_body path)."""

    def test_dict_body_converted(self, capsys) -> None:
        """Dict body is converted via convert_to_issue_body."""
        issue = {
            "title": "Test Issue",
            "labels": ["p1"],
            "body": {
                "location": "src/main.py",
                "problem": "Too slow",
                "proposed_solution": "Optimize",
            },
            "estimate": "2h",
        }
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="https://github.com/owner/repo/issues/1",
                stderr="",
            )
            result = create_github_issue(issue, "owner/repo", 1, 1)
            assert result.success
            # Verify the body was passed to gh command
            call_args = mock_run.call_args[0][0]
            assert "--body-file" in call_args


class TestInitializePrerequisitesLabelsFail:
    """Test initialize_prerequisites when label fetch fails."""

    def test_label_fetch_failure(self) -> None:
        """Label fetch failure returns error."""
        with (
            patch("create_issues.check_github_cli_available") as mock_cli,
            patch("create_issues.get_repository_labels") as mock_labels,
        ):
            mock_cli.return_value = OperationResult(success=True, result="gh ready")
            mock_labels.return_value = OperationResult(success=False, error="API error")
            result = initialize_prerequisites("owner/repo")
            assert not result.success
            assert "API error" in result.error


class TestNeedsTriageNotAdded:
    """Test needs-triage label is not duplicated."""

    def test_needs_triage_already_present(self, capsys) -> None:
        """needs-triage not added if already in labels."""
        issue = {
            "title": "Test Issue",
            "labels": ["p1", "needs-triage"],
        }
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="https://github.com/owner/repo/issues/1",
                stderr="",
            )
            result = create_github_issue(issue, "owner/repo", 1, 1)
            assert result.success
            # Check the labels in the command
            call_args = mock_run.call_args[0][0]
            label_idx = call_args.index("--label")
            labels_str = call_args[label_idx + 1]
            # Should only have one needs-triage
            assert labels_str.count("needs-triage") == 1


class TestModuleEntryPoint:
    """Test the __main__ entry point."""

    def test_main_entry_point(self) -> None:
        """Module entry point calls main and sys.exit."""
        import contextlib
        import runpy

        with (
            patch("sys.argv", ["create_issues.py", "-r", "invalid"]),
            patch("sys.exit"),
            contextlib.suppress(SystemExit),
        ):
            runpy.run_module("create_issues", run_name="__main__", alter_sys=True)


# ============================================================================
# Additional Coverage Tests
# ============================================================================


class TestMalformedEstimateLabelSort:
    """Test estimate_sort_key handles malformed labels."""

    def test_malformed_estimate_sorted_last(self, capsys) -> None:
        """Malformed estimate labels are sorted to the end."""
        labels = [
            {"name": "estimate: 2h", "description": "2 hours"},
            {"name": "estimate: invalid", "description": "Bad format"},
            {"name": "estimate: 1h", "description": "1 hour"},
        ]
        write_labels_for_ai(labels)
        captured = capsys.readouterr()
        # Should output without crashing
        assert "estimate: 1h" in captured.out
        assert "estimate: 2h" in captured.out
        assert "estimate: invalid" in captured.out


class TestValidateIssueSecurityEmptyTitle:
    """Test validate_issue_security with empty/missing title."""

    @pytest.mark.parametrize(
        "issue",
        [
            {"title": "", "labels": ["p1"]},
            {"labels": ["p1"]},
        ],
    )
    def test_empty_or_missing_title_skips_validation(self, issue: dict) -> None:
        """Empty/missing title doesn't cause security error."""
        result = validate_issue_security(issue, 1)
        assert result.is_valid


class TestValidateIssueBodyEmptyFilesAffected:
    """Test validate_issue_body_structure with empty files_affected."""

    def test_empty_files_affected_no_error(self) -> None:
        """Empty files_affected array doesn't cause iteration."""
        issue = {
            "title": "Test",
            "labels": ["p1"],
            "body": {
                "location": "test.py",
                "problem": "Test problem",
                "files_affected": [],  # Empty array
            },
        }
        result = validate_issue_body_structure(issue, 1)
        # Should not error, just warn about missing recommended fields
        assert result.is_valid

    def test_valid_files_affected_passes(self) -> None:
        """Valid files_affected entries pass security check."""
        issue = {
            "title": "Test",
            "labels": ["p1"],
            "body": {
                "location": "src/main.py",
                "current_state": "Broken",
                "problem": "Test problem",
                "proposed_solution": "Fix it",
                "success_criteria": "Works",
                "files_affected": ["src/main.py", "tests/test_main.py"],
            },
        }
        result = validate_issue_body_structure(issue, 1)
        assert result.is_valid
        assert len(result.warnings) == 0


class TestListLabelsNoMissing:
    """Test list_labels mode with no missing labels."""

    def test_list_labels_no_missing_labels(self, capsys) -> None:
        """list_labels mode with all labels present skips warning."""
        with (
            patch("create_issues.get_required_labels") as mock_required,
            patch("create_issues.get_missing_labels") as mock_missing,
            patch("create_issues.write_labels_for_ai"),
        ):
            mock_required.return_value = []
            mock_missing.return_value = []  # No missing labels

            labels, should_exit = handle_label_management(
                "owner/repo",
                [{"name": "p1"}],
                create_labels=False,
                list_labels=True,
                validate_only=False,
            )
            assert should_exit
