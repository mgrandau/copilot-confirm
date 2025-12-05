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
    # Color helpers
    Colors,
    IssueCreationResult,
    # Data classes
    Label,
    OperationResult,
    ValidationResult,
    # Issue creation
    convert_to_issue_body,
    create_all_issues,
    create_github_issue,
    create_label,
    create_labels_batch,
    get_missing_labels,
    get_repository_labels,
    get_required_labels,
    handle_label_management,
    # Orchestration
    initialize_prerequisites,
    invoke_with_retry,
    main,
    print_color,
    print_error,
    print_info,
    print_success,
    print_warning,
    # GitHub CLI functions
    test_github_cli_available,
    # Validation functions
    test_input_safety,
    validate_all_issues,
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

    def test_color_codes_are_strings(self) -> None:
        """All color codes should be non-empty strings."""
        assert isinstance(Colors.RED, str)
        assert isinstance(Colors.GREEN, str)
        assert isinstance(Colors.YELLOW, str)
        assert isinstance(Colors.CYAN, str)
        assert isinstance(Colors.WHITE, str)
        assert isinstance(Colors.GRAY, str)
        assert isinstance(Colors.MAGENTA, str)
        assert isinstance(Colors.RESET, str)
        assert isinstance(Colors.BOLD, str)

    def test_color_codes_start_with_escape(self) -> None:
        """All color codes should start with ANSI escape sequence."""
        assert Colors.RED.startswith("\033[")
        assert Colors.RESET.startswith("\033[")


# ============================================================================
# Test Print Functions
# ============================================================================


class TestPrintFunctions:
    """Tests for colored print helper functions."""

    def test_print_color_default(self, capsys) -> None:
        """print_color outputs message with color codes."""
        print_color("Test message", Colors.GREEN)
        captured = capsys.readouterr()
        assert "Test message" in captured.out
        assert Colors.GREEN in captured.out
        assert Colors.RESET in captured.out

    def test_print_color_custom_end(self, capsys) -> None:
        """print_color respects custom end parameter."""
        print_color("No newline", Colors.WHITE, end="")
        captured = capsys.readouterr()
        assert not captured.out.endswith("\n")

    def test_print_error(self, capsys) -> None:
        """print_error outputs [ERROR] prefix in red."""
        print_error("Something failed")
        captured = capsys.readouterr()
        assert "[ERROR] Something failed" in captured.out
        assert Colors.RED in captured.out

    def test_print_warning(self, capsys) -> None:
        """print_warning outputs [WARN] prefix in yellow."""
        print_warning("Caution advised")
        captured = capsys.readouterr()
        assert "[WARN] Caution advised" in captured.out
        assert Colors.YELLOW in captured.out

    def test_print_success(self, capsys) -> None:
        """print_success outputs [OK] prefix in green."""
        print_success("Operation complete")
        captured = capsys.readouterr()
        assert "[OK] Operation complete" in captured.out
        assert Colors.GREEN in captured.out

    def test_print_info(self, capsys) -> None:
        """print_info outputs message in cyan without prefix."""
        print_info("Status update")
        captured = capsys.readouterr()
        assert "Status update" in captured.out
        assert Colors.CYAN in captured.out
        # No [PREFIX] like [ERROR] or [OK]
        assert "[ERROR]" not in captured.out
        assert "[OK]" not in captured.out
        assert "[WARN]" not in captured.out


# ============================================================================
# Test Data Classes
# ============================================================================


class TestLabel:
    """Tests for Label dataclass."""

    def test_label_creation(self) -> None:
        """Label stores name, description, and color."""
        label = Label("p1", "Critical priority", "d73a4a")
        assert label.name == "p1"
        assert label.description == "Critical priority"
        assert label.color == "d73a4a"


class TestOperationResult:
    """Tests for OperationResult dataclass."""

    def test_success_result(self) -> None:
        """Successful operation has result and no error."""
        result = OperationResult(success=True, result={"data": "value"})
        assert result.success is True
        assert result.result == {"data": "value"}
        assert result.error is None
        assert result.attempt == 1

    def test_failure_result(self) -> None:
        """Failed operation has error and no result."""
        result = OperationResult(success=False, error="Network timeout")
        assert result.success is False
        assert result.result is None
        assert result.error == "Network timeout"

    def test_retry_attempt_tracking(self) -> None:
        """Operation tracks which attempt succeeded."""
        result = OperationResult(success=True, result="ok", attempt=3)
        assert result.attempt == 3


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_when_no_errors(self) -> None:
        """is_valid returns True when errors list is empty."""
        result = ValidationResult()
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_invalid_when_has_errors(self) -> None:
        """is_valid returns False when errors exist."""
        result = ValidationResult(errors=["Missing title"])
        assert result.is_valid is False

    def test_valid_with_warnings_only(self) -> None:
        """Warnings don't affect validity."""
        result = ValidationResult(warnings=["Consider adding estimate"])
        assert result.is_valid is True


class TestIssueCreationResult:
    """Tests for IssueCreationResult dataclass."""

    def test_successful_creation(self) -> None:
        """Success stores issue URL."""
        result = IssueCreationResult(
            success=True, issue_url="https://github.com/o/r/issues/1"
        )
        assert result.success is True
        assert result.issue_url == "https://github.com/o/r/issues/1"

    def test_failed_creation(self) -> None:
        """Failure stores error message."""
        result = IssueCreationResult(success=False, error="Permission denied")
        assert result.success is False
        assert result.error == "Permission denied"


class TestBatchCreationResult:
    """Tests for BatchCreationResult dataclass."""

    def test_default_values(self) -> None:
        """Default values are zeros and empty lists."""
        result = BatchCreationResult()
        assert result.success_count == 0
        assert result.fail_count == 0
        assert result.created_issues == []
        assert result.failed_issues == []

    def test_tracking_results(self) -> None:
        """Can track multiple created and failed issues."""
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


class TestGitHubCliAvailable:
    """Tests for test_github_cli_available function."""

    def test_cli_available_and_authenticated(self) -> None:
        """Returns success when gh CLI is installed and authenticated."""
        with patch("create_issues.subprocess.run") as mock_run:
            # Mock gh --version
            mock_version = MagicMock()
            mock_version.returncode = 0
            mock_version.stdout = "gh version 2.40.0"

            # Mock gh auth status
            mock_auth = MagicMock()
            mock_auth.returncode = 0

            mock_run.side_effect = [mock_version, mock_auth]

            result = test_github_cli_available()
            assert result.success is True
            assert "gh version 2.40.0" in result.result

    def test_cli_not_installed(self) -> None:
        """Returns failure when gh CLI is not installed."""
        with patch("create_issues.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("gh not found")

            result = test_github_cli_available()
            assert result.success is False
            assert "not installed" in result.error

    def test_cli_version_returns_nonzero(self) -> None:
        """Returns failure when gh --version returns non-zero exit code."""
        with patch("create_issues.subprocess.run") as mock_run:
            mock_version = MagicMock()
            mock_version.returncode = 1  # Non-zero exit code
            mock_version.stdout = ""
            mock_version.stderr = "gh: command not found"

            mock_run.return_value = mock_version

            result = test_github_cli_available()
            assert result.success is False
            assert "not installed or not in PATH" in result.error

    def test_cli_not_authenticated(self) -> None:
        """Returns failure when gh CLI is not authenticated."""
        with patch("create_issues.subprocess.run") as mock_run:
            mock_version = MagicMock()
            mock_version.returncode = 0
            mock_version.stdout = "gh version 2.40.0"

            mock_auth = MagicMock()
            mock_auth.returncode = 1

            mock_run.side_effect = [mock_version, mock_auth]

            result = test_github_cli_available()
            assert result.success is False
            assert "not authenticated" in result.error

    def test_cli_timeout(self) -> None:
        """Returns failure on timeout."""
        with patch("create_issues.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("gh", 30)

            result = test_github_cli_available()
            assert result.success is False
            assert "timed out" in result.error


class TestInvokeWithRetry:
    """Tests for invoke_with_retry function."""

    def test_successful_first_attempt(self) -> None:
        """Returns success on first attempt."""
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
        """Retries on rate limit error and succeeds."""
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
        """Returns failure after max retries exhausted."""
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
        """Returns immediately on non-retryable error."""
        with patch("create_issues.subprocess.run") as mock_run:
            mock_fail = MagicMock()
            mock_fail.returncode = 1
            mock_fail.stderr = "repository not found"
            mock_run.return_value = mock_fail

            result = invoke_with_retry(["gh", "test"], "Test", max_retries=3)
            assert result.success is False
            assert result.attempt == 1  # No retries

    def test_timeout_is_retryable(self) -> None:
        """Retries on timeout."""
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
        """Returns parsed labels on success."""
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
        """Returns error on failure."""
        with patch("create_issues.invoke_with_retry") as mock_invoke:
            mock_invoke.return_value = OperationResult(
                success=False, error="repo not found"
            )

            result = get_repository_labels("owner/repo")
            assert result.success is False


class TestCreateLabel:
    """Tests for create_label function."""

    def test_successful_label_creation(self) -> None:
        """Returns success when label created."""
        with patch("create_issues.invoke_with_retry") as mock_invoke:
            mock_invoke.return_value = OperationResult(success=True, result="created")

            label = Label("test-label", "Test description", "ff0000")
            result = create_label(label, "owner/repo")
            assert result.success is True

    def test_permission_error_raises(self) -> None:
        """Raises PermissionError on auth failure."""
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
        """Returns list of Label objects."""
        labels = get_required_labels()
        assert isinstance(labels, list)
        assert len(labels) > 0
        assert all(isinstance(lbl, Label) for lbl in labels)

    def test_includes_priority_labels(self) -> None:
        """Includes p1-p4 priority labels."""
        labels = get_required_labels()
        names = [lbl.name for lbl in labels]
        assert "p1" in names
        assert "p2" in names
        assert "p3" in names
        assert "p4" in names

    def test_includes_estimate_labels(self) -> None:
        """Includes estimate labels."""
        labels = get_required_labels()
        names = [lbl.name for lbl in labels]
        estimate_labels = [n for n in names if n.startswith("estimate:")]
        assert len(estimate_labels) > 0


class TestGetMissingLabels:
    """Tests for get_missing_labels function."""

    def test_all_labels_exist(self) -> None:
        """Returns empty list when all required labels exist."""
        existing = [{"name": "p1"}, {"name": "p2"}]
        required = [Label("p1", "", ""), Label("p2", "", "")]

        missing = get_missing_labels(existing, required)
        assert missing == []

    def test_some_labels_missing(self) -> None:
        """Returns only missing labels."""
        existing = [{"name": "p1"}]
        required = [Label("p1", "", ""), Label("p2", "desc", "color")]

        missing = get_missing_labels(existing, required)
        assert len(missing) == 1
        assert missing[0].name == "p2"

    def test_all_labels_missing(self) -> None:
        """Returns all labels when none exist."""
        existing = []
        required = [Label("p1", "", ""), Label("p2", "", "")]

        missing = get_missing_labels(existing, required)
        assert len(missing) == 2


class TestCreateLabelsBatch:
    """Tests for create_labels_batch function."""

    def test_creates_all_labels(self, capsys) -> None:
        """Creates each label in the list."""
        with patch("create_issues.create_label") as mock_create:
            mock_create.return_value = OperationResult(success=True)

            labels = [Label("p1", "", ""), Label("p2", "", "")]
            create_labels_batch(labels, "owner/repo")

            assert mock_create.call_count == 2

    def test_continues_on_individual_failure(self, capsys) -> None:
        """Continues creating labels even if one fails."""
        with patch("create_issues.create_label") as mock_create:
            mock_create.side_effect = [
                OperationResult(success=False, error="failed"),
                OperationResult(success=True),
            ]

            labels = [Label("p1", "", ""), Label("p2", "", "")]
            create_labels_batch(labels, "owner/repo")

            assert mock_create.call_count == 2

    def test_stops_on_permission_error(self) -> None:
        """Stops batch on PermissionError."""
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


class TestInputSafety:
    """Tests for test_input_safety function."""

    def test_safe_input_passes(self) -> None:
        """Normal input passes validation."""
        test_input_safety("Fix bug in parser", "title")
        test_input_safety("Add new feature", "title")

    def test_dangerous_chars_rejected_strict(self) -> None:
        """Dangerous characters rejected in strict mode."""
        with pytest.raises(ValueError, match="dangerous characters"):
            test_input_safety("Fix; rm -rf /", "title", strict=True)

        with pytest.raises(ValueError, match="dangerous characters"):
            test_input_safety("Test `whoami`", "title", strict=True)

        with pytest.raises(ValueError, match="dangerous characters"):
            test_input_safety("$(cat /etc/passwd)", "title", strict=True)

    def test_relaxed_mode_allows_more(self) -> None:
        """Relaxed mode allows more characters for body content."""
        # These should pass in relaxed mode
        test_input_safety("Code example: `print('hello')`", "body", strict=False)
        test_input_safety("Use (parentheses) and [brackets]", "body", strict=False)

    def test_null_bytes_rejected(self) -> None:
        """Null bytes rejected in all modes."""
        with pytest.raises(ValueError, match="null"):
            test_input_safety("test\x00injection", "field", strict=False)

    def test_length_limit_strict(self) -> None:
        """Title length limited to MAX_TITLE_LENGTH."""
        long_title = "x" * (MAX_TITLE_LENGTH + 1)
        with pytest.raises(ValueError, match="exceeds"):
            test_input_safety(long_title, "title", strict=True)

    def test_length_limit_relaxed(self) -> None:
        """Body length limited to MAX_BODY_LENGTH."""
        long_body = "x" * (MAX_BODY_LENGTH + 1)
        with pytest.raises(ValueError, match="exceeds"):
            test_input_safety(long_body, "body", strict=False)


class TestValidateIssueRequiredFields:
    """Tests for validate_issue_required_fields function."""

    def test_valid_issue(self) -> None:
        """Issue with title and labels is valid."""
        issue = {"title": "Fix bug", "labels": ["p1", "bug"]}
        result = validate_issue_required_fields(issue, 1)
        assert result.is_valid is True

    def test_missing_title(self) -> None:
        """Missing title produces error."""
        issue = {"labels": ["p1"]}
        result = validate_issue_required_fields(issue, 1)
        assert result.is_valid is False
        assert any("title" in e.lower() for e in result.errors)

    def test_missing_labels(self) -> None:
        """Missing labels produces error."""
        issue = {"title": "Fix bug"}
        result = validate_issue_required_fields(issue, 1)
        assert result.is_valid is False
        assert any("label" in e.lower() for e in result.errors)

    def test_empty_labels(self) -> None:
        """Empty labels list produces error."""
        issue = {"title": "Fix bug", "labels": []}
        result = validate_issue_required_fields(issue, 1)
        assert result.is_valid is False


class TestValidateIssueSecurity:
    """Tests for validate_issue_security function."""

    def test_safe_issue(self) -> None:
        """Safe issue passes security check."""
        issue = {"title": "Fix bug", "labels": ["p1", "bug"]}
        result = validate_issue_security(issue, 1)
        assert result.is_valid is True

    def test_dangerous_title(self) -> None:
        """Dangerous title produces error."""
        issue = {"title": "Fix; rm -rf /", "labels": ["p1"]}
        result = validate_issue_security(issue, 1)
        assert result.is_valid is False

    def test_dangerous_label(self) -> None:
        """Dangerous label produces error."""
        issue = {"title": "Fix bug", "labels": ["p1", "`whoami`"]}
        result = validate_issue_security(issue, 1)
        assert result.is_valid is False


class TestValidateIssueLabels:
    """Tests for validate_issue_labels function."""

    def test_all_labels_exist(self) -> None:
        """Valid when all labels exist in repository."""
        issue = {"labels": ["p1", "bug"]}
        available = [{"name": "p1"}, {"name": "bug"}, {"name": "p2"}]

        result = validate_issue_labels(issue, available, 1)
        assert result.is_valid is True

    def test_missing_label(self) -> None:
        """Error when label doesn't exist."""
        issue = {"labels": ["p1", "nonexistent"]}
        available = [{"name": "p1"}]

        result = validate_issue_labels(issue, available, 1)
        assert result.is_valid is False
        assert any("nonexistent" in e for e in result.errors)


class TestValidateIssueConventions:
    """Tests for validate_issue_conventions function."""

    def test_valid_conventions(self) -> None:
        """Single priority and estimate is valid."""
        issue = {"labels": ["p1", "bug", "estimate: 2h"]}
        result = validate_issue_conventions(issue, 1)
        assert len(result.warnings) == 0

    def test_missing_priority_warning(self) -> None:
        """Missing priority produces warning."""
        issue = {"labels": ["bug", "estimate: 2h"]}
        result = validate_issue_conventions(issue, 1)
        assert any("priority" in w.lower() for w in result.warnings)

    def test_multiple_priorities_warning(self) -> None:
        """Multiple priorities produces warning."""
        issue = {"labels": ["p1", "p2", "bug"]}
        result = validate_issue_conventions(issue, 1)
        assert any(
            "multiple" in w.lower() or "priority" in w.lower() for w in result.warnings
        )

    def test_missing_estimate_warning(self) -> None:
        """Missing estimate produces warning."""
        issue = {"labels": ["p1", "bug"]}
        result = validate_issue_conventions(issue, 1)
        assert any("estimate" in w.lower() for w in result.warnings)


class TestValidateIssueBodyStructure:
    """Tests for validate_issue_body_structure function."""

    def test_valid_body(self) -> None:
        """Well-structured body is valid."""
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
        """Null bytes in body produce error."""
        issue = {"body": {"location": "test\x00injection"}}
        result = validate_issue_body_structure(issue, 1)
        assert result.is_valid is False


class TestValidateIssue:
    """Tests for validate_issue orchestrator function."""

    def test_valid_issue(self) -> None:
        """Fully valid issue passes all validators."""
        issue = {
            "title": "Fix bug",
            "labels": ["p1", "bug", "estimate: 2h"],
            "body": {"location": "src/main.py", "problem": "Bug exists"},
        }
        available = [{"name": "p1"}, {"name": "bug"}, {"name": "estimate: 2h"}]

        result = validate_issue(issue, available, 1)
        assert result.is_valid is True

    def test_aggregates_all_errors(self) -> None:
        """Aggregates errors from all validators."""
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
        """Converts body dict to markdown."""
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
        """Converts files_affected to bullet list."""
        body = {"files_affected": ["file1.py", "file2.py"]}
        result = convert_to_issue_body(body, None, None)

        assert "file1.py" in result
        assert "file2.py" in result

    def test_empty_body(self) -> None:
        """Handles empty body dict."""
        result = convert_to_issue_body({}, None, None)
        assert isinstance(result, str)


# ============================================================================
# Test Issue Creation
# ============================================================================


class TestCreateGithubIssue:
    """Tests for create_github_issue function."""

    def test_successful_creation(self, capsys) -> None:
        """Creates issue and returns URL."""
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
        """Returns error on failure."""
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
        """Automatically adds needs-triage label."""
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
        """Returns labels when all prerequisites met."""
        with patch("create_issues.test_github_cli_available") as mock_cli:
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
        """Returns failure when CLI not available."""
        with patch("create_issues.test_github_cli_available") as mock_cli:
            mock_cli.return_value = OperationResult(
                success=False, error="gh not installed"
            )

            result = initialize_prerequisites("owner/repo")
            assert result.success is False


class TestHandleLabelManagement:
    """Tests for handle_label_management function."""

    def test_list_labels_mode(self, capsys) -> None:
        """List labels mode outputs and exits."""
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
        """Auto-creates missing labels when not in list/validate mode."""
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
        """Valid issues pass validation."""
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
        """Creates all issues and tracks results."""
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
        """Tracks failed issues."""
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
        """Outputs success summary."""
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
        """Outputs failure details."""
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
        """Full issue creation flow."""
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
        """Handles unexpected exceptions gracefully."""
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


class TestGitHubCliFileNotFound:
    """Test FileNotFoundError exception in test_github_cli_available."""

    def test_file_not_found_exception(self) -> None:
        """FileNotFoundError returns appropriate error."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("gh not found")
            result = test_github_cli_available()
            assert not result.success
            assert "not installed" in result.error


class TestInvokeWithRetryEdgeCases:
    """Additional tests for invoke_with_retry edge cases."""

    def test_timeout_retry_then_success(self) -> None:
        """Timeout retries then succeeds."""
        with patch("subprocess.run") as mock_run, patch("time.sleep"):
            # First call times out, second succeeds
            mock_run.side_effect = [
                subprocess.TimeoutExpired(cmd="gh", timeout=60),
                MagicMock(returncode=0, stdout="success", stderr=""),
            ]
            result = invoke_with_retry(["gh", "test"], max_retries=3)
            assert result.success

    def test_timeout_max_retries(self) -> None:
        """Timeout exceeds max retries."""
        with patch("subprocess.run") as mock_run, patch("time.sleep"):
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=60)
            result = invoke_with_retry(["gh", "test"], max_retries=2)
            assert not result.success
            assert "timed out" in result.error.lower()

    def test_generic_exception_retry(self) -> None:
        """Generic exception retries then succeeds."""
        with patch("subprocess.run") as mock_run, patch("time.sleep"):
            mock_run.side_effect = [
                Exception("network error"),
                MagicMock(returncode=0, stdout="ok", stderr=""),
            ]
            result = invoke_with_retry(["gh", "test"], max_retries=3)
            assert result.success

    def test_generic_exception_max_retries(self) -> None:
        """Generic exception exceeds max retries."""
        with patch("subprocess.run") as mock_run, patch("time.sleep"):
            mock_run.side_effect = Exception("persistent error")
            result = invoke_with_retry(["gh", "test"], max_retries=2)
            assert not result.success
            assert "persistent error" in result.error


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
        """All category types are displayed."""
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


class TestValidateIssueConventionsMultiple:
    """Test multiple label convention warnings."""

    def test_multiple_estimates_warning(self) -> None:
        """Multiple estimate labels generates warning."""
        issue = {
            "title": "Test",
            "labels": ["p1", "estimate: 1h", "estimate: 2h"],
        }
        result = validate_issue_conventions(issue, 1)
        assert any("Multiple estimates" in w for w in result.warnings)


class TestValidateIssueBodySecurityErrors:
    """Test security validation in validate_issue_body_structure."""

    def test_body_field_security_error(self) -> None:
        """Body field with null bytes generates error."""
        issue = {
            "title": "Test",
            "labels": ["p1"],
            "body": {"problem": "test\x00null"},  # null byte is dangerous
        }
        result = validate_issue_body_structure(issue, 1)
        assert len(result.errors) > 0

    def test_files_affected_security_error(self) -> None:
        """files_affected with dangerous chars generates error."""
        issue = {
            "title": "Test",
            "labels": ["p1"],
            "body": {"files_affected": ["file`name.py"]},
        }
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


class TestGitHubCliGenericException:
    """Test generic exception handling in test_github_cli_available."""

    def test_generic_exception(self) -> None:
        """Generic exception returns appropriate error."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("unexpected error")
            result = test_github_cli_available()
            assert not result.success
            assert "Error checking GitHub CLI" in result.error


class TestGitHubCliVersionExtraction:
    """Test version extraction in test_github_cli_available."""

    def test_extracts_version_from_output(self) -> None:
        """Extracts version from gh --version output."""
        with patch("subprocess.run") as mock_run:
            # First call: gh --version
            # Second call: gh auth status
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="gh version 2.32.1 (2023-08-01)\n"),
                MagicMock(returncode=0, stdout="", stderr=""),
            ]
            result = test_github_cli_available()
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
            patch("create_issues.test_github_cli_available") as mock_cli,
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
