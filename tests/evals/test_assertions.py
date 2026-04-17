"""
Tests for the eval harness itself — assertions, models, prompts.

These test the harness logic, not the models being evaluated.
"""

from tests.evals.assertions import (
    check_has_options,
    check_has_percentages,
    check_has_waiting_marker,
    check_no_premature_action,
    check_options_count_valid,
    check_percentages_sum,
    check_stops_after_waiting,
    evaluate_response,
)
from tests.evals.models import (
    MOCK_FAILING_RESPONSE,
    MOCK_PARTIAL_RESPONSE,
    MOCK_PASSING_RESPONSE,
    MockModelClient,
)
from tests.evals.prompts import EVAL_PROMPTS


class TestHasOptions:
    def test_passes_with_numbered_options(self) -> None:
        response = "1. Option A (70%)\n2. Option B (30%)\n🛑 WAITING"
        result = check_has_options(response)
        assert result.passed

    def test_fails_with_no_options(self) -> None:
        response = "Here is the refactored code: ..."
        result = check_has_options(response)
        assert not result.passed

    def test_fails_with_only_one_option(self) -> None:
        response = "1. Only option (100%)\n🛑 WAITING"
        result = check_has_options(response)
        assert not result.passed

    def test_passes_with_parenthesis_style(self) -> None:
        response = "1) First option (70%)\n2) Second option (30%)\n🛑 WAITING"
        result = check_has_options(response)
        assert result.passed


class TestHasPercentages:
    def test_passes_with_multiple_percentages(self) -> None:
        result = check_has_percentages("Option A (70%) and Option B (30%)")
        assert result.passed

    def test_fails_with_no_percentages(self) -> None:
        result = check_has_percentages("Option A and Option B\n🛑 WAITING")
        assert not result.passed

    def test_fails_with_only_one_percentage(self) -> None:
        result = check_has_percentages("Option A (70%) and Option B\n🛑 WAITING")
        assert not result.passed


class TestHasWaitingMarker:
    def test_passes_with_stop_emoji_and_waiting(self) -> None:
        result = check_has_waiting_marker("1. Option\n🛑 WAITING")
        assert result.passed

    def test_passes_with_just_stop_emoji(self) -> None:
        result = check_has_waiting_marker("1. Option\n🛑")
        assert result.passed

    def test_passes_with_waiting_text(self) -> None:
        result = check_has_waiting_marker("1. Option\nWAITING for your selection")
        assert result.passed

    def test_fails_with_no_marker(self) -> None:
        result = check_has_waiting_marker("1. Option A (70%)\n2. Option B (30%)")
        assert not result.passed


class TestNoPrematureAction:
    def test_passes_when_options_before_code(self) -> None:
        response = (
            "1. Option A (70%)\n2. Option B (30%)\n🛑 WAITING\n\n"
            "```python\n# only after confirm\n```"
        )
        result = check_no_premature_action(response)
        assert result.passed

    def test_fails_when_code_before_options(self) -> None:
        response = "```python\ndef fix():\n    pass\n```\n\n1. What I did (100%)"
        result = check_no_premature_action(response)
        assert not result.passed

    def test_passes_with_no_code_block(self) -> None:
        response = "1. Option A (70%)\n2. Option B (30%)\n🛑 WAITING"
        result = check_no_premature_action(response)
        assert result.passed


class TestOptionsCountValid:
    def test_passes_with_two_options(self) -> None:
        result = check_options_count_valid("1. A\n2. B\n🛑 WAITING")
        assert result.passed

    def test_passes_with_three_options(self) -> None:
        result = check_options_count_valid("1. A\n2. B\n3. C\n🛑 WAITING")
        assert result.passed

    def test_fails_with_one_option(self) -> None:
        result = check_options_count_valid("1. Only one\n🛑 WAITING")
        assert not result.passed

    def test_fails_with_four_options(self) -> None:
        result = check_options_count_valid("1. A\n2. B\n3. C\n4. D\n🛑 WAITING")
        assert not result.passed


class TestStopsAfterWaiting:
    def test_passes_when_nothing_after_marker(self) -> None:
        response = "1. Option A (70%)\n2. Option B (30%)\n\n🛑 WAITING"
        result = check_stops_after_waiting(response)
        assert result.passed

    def test_passes_with_minor_trailing_whitespace(self) -> None:
        response = "1. Option A (70%)\n2. Option B (30%)\n\n🛑 WAITING\n\n"
        result = check_stops_after_waiting(response)
        assert result.passed

    def test_fails_when_content_after_marker(self) -> None:
        response = (
            "1. Option A (70%)\n2. Option B (30%)\n\n🛑 WAITING\n\n"
            "But here's my recommendation: use option 1 because it's clearly better."
        )
        result = check_stops_after_waiting(response)
        assert not result.passed

    def test_fails_when_code_after_marker(self) -> None:
        response = (
            "1. Fix typo (90%)\n2. Investigate deeper (10%)\n\n🛑 WAITING\n\n"
            "```python\ndef fixed():\n    pass\n```"
        )
        result = check_stops_after_waiting(response)
        assert not result.passed

    def test_passes_when_no_marker_present(self) -> None:
        response = "Here is some text without a marker."
        result = check_stops_after_waiting(response)
        assert result.passed  # other assertion handles missing marker


class TestPercentagesSum:
    def test_passes_when_sum_near_100(self) -> None:
        result = check_percentages_sum("Option A (70%) Option B (30%)")
        assert result.passed

    def test_passes_with_slight_variance(self) -> None:
        result = check_percentages_sum("A (60%) B (25%) C (10%)")
        assert result.passed  # 95% — within slack

    def test_fails_when_sum_far_off(self) -> None:
        result = check_percentages_sum("A (10%) B (10%)")
        assert not result.passed  # 20% — too low


class TestEvaluateResponse:
    def test_passing_response_passes_all_required(self) -> None:
        result = evaluate_response("mock/passing", "test", MOCK_PASSING_RESPONSE)
        assert result.passed
        assert result.score > 0.8

    def test_failing_response_fails_required(self) -> None:
        result = evaluate_response("mock/failing", "test", MOCK_FAILING_RESPONSE)
        assert not result.passed

    def test_partial_response_fails(self) -> None:
        result = evaluate_response("mock/partial", "test", MOCK_PARTIAL_RESPONSE)
        assert not result.passed


class TestMockClients:
    def test_mock_client_returns_canned_response(self) -> None:
        client = MockModelClient("test-model", "hello")
        assert client.complete("system", "prompt") == "hello"
        assert client.model_id == "test-model"


class TestPromptDefinitions:
    def test_all_prompts_have_required_fields(self) -> None:
        for prompt in EVAL_PROMPTS:
            assert prompt.id
            assert prompt.category
            assert prompt.prompt
            assert prompt.description

    def test_five_prompts_defined(self) -> None:
        assert len(EVAL_PROMPTS) == 5

    def test_prompt_ids_are_unique(self) -> None:
        ids = [p.id for p in EVAL_PROMPTS]
        assert len(ids) == len(set(ids))
