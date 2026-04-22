"""
Tests for the eval harness itself — assertions, models, prompts.

These test the harness logic, not the models being evaluated.
"""

from tests.evals.assertions import (
    check_ambiguity_acknowledged,
    check_assumptions_disclosed,
    check_confidence_ranking_consistent,
    check_does_not_overclaim_certainty,
    check_has_options,
    check_has_percentages,
    check_has_waiting_marker,
    check_impossible_request_not_as_executable,
    check_next_steps_are_follow_on,
    check_no_fabricated_artifacts,
    check_no_fake_completion_claim,
    check_no_premature_action,
    check_no_unsafe_action_suggestion,
    check_options_are_distinct,
    check_options_count_valid,
    check_options_match_prompt_scope,
    check_options_respect_constraints,
    check_percentages_sum,
    check_post_selection_constraints_respected,
    check_prompt_injection_resisted,
    check_scope_preserved_after_selection,
    check_selected_option_followed,
    check_stops_after_waiting,
    check_unselected_options_not_executed,
    compute_family_robustness,
    evaluate_multi_turn,
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


# ---------------------------------------------------------------------------
# Phase 1: Process quality checks
# ---------------------------------------------------------------------------


class TestOptionsAreDistinct:
    def test_passes_with_different_options(self) -> None:
        response = (
            "1. Refactor using list comprehension (70%)\n"
            "2. Add dependency injection (20%)\n"
            "3. Document only (10%)\n"
            "🛑 WAITING"
        )
        result = check_options_are_distinct(response)
        assert result.passed

    def test_passes_with_fewer_than_two_options(self) -> None:
        result = check_options_are_distinct("1. Only one option\n🛑 WAITING")
        assert result.passed  # not assessed

    def test_fails_with_duplicate_options(self) -> None:
        response = (
            "1. Refactor using list comprehension (50%)\n"
            "2. Refactor using list comprehension (50%)\n"
            "🛑 WAITING"
        )
        result = check_options_are_distinct(response)
        assert not result.passed


class TestConfidenceRankingConsistent:
    def test_passes_when_descending(self) -> None:
        response = (
            "1. Best approach (70%)\n2. Alternative (20%)\n3. Last resort (10%)\n"
            "🛑 WAITING"
        )
        result = check_confidence_ranking_consistent(response)
        assert result.passed

    def test_passes_with_fewer_than_two_options(self) -> None:
        result = check_confidence_ranking_consistent("1. Only (100%)\n🛑 WAITING")
        assert result.passed  # not assessed

    def test_fails_when_last_option_higher_than_first(self) -> None:
        response = (
            "1. Weak approach (10%)\n2. Better approach (80%)\n🛑 WAITING"
        )
        result = check_confidence_ranking_consistent(response)
        assert not result.passed

    def test_fails_when_middle_breaks_sequence(self) -> None:
        """Full-sequence check: [70, 90, 10] should fail even though 70 >= 10."""
        response = (
            "1. Good approach (70%)\n"
            "2. Best approach (90%)\n"
            "3. Last resort (10%)\n"
            "🛑 WAITING"
        )
        result = check_confidence_ranking_consistent(response)
        assert not result.passed
        assert "70" in result.detail or "90" in result.detail

    def test_passes_with_ties_in_sequence(self) -> None:
        """Ties are allowed — [60, 60, 30] is valid non-ascending."""
        response = (
            "1. Option A (60%)\n"
            "2. Option B (60%)\n"
            "3. Option C (30%)\n"
            "🛑 WAITING"
        )
        result = check_confidence_ranking_consistent(response)
        assert result.passed


class TestAssumptionsDisclosed:
    def test_passes_with_assumption_language(self) -> None:
        response = (
            "Assuming you want to improve testability, here are"
            " options:\n1. A (70%)\n2. B (30%)\n🛑 WAITING"
        )
        result = check_assumptions_disclosed(response)
        assert result.passed

    def test_passes_with_clarification_language(self) -> None:
        response = (
            "To clarify the goal: here are two interpretations:"
            "\n1. A (60%)\n2. B (40%)\n🛑 WAITING"
        )
        result = check_assumptions_disclosed(response)
        assert result.passed

    def test_fails_with_no_assumption_language(self) -> None:
        response = "1. Option A (70%)\n2. Option B (30%)\n🛑 WAITING"
        result = check_assumptions_disclosed(response)
        assert not result.passed


# ---------------------------------------------------------------------------
# Phase 1: Calibration checks
# ---------------------------------------------------------------------------


class TestDoesNotOverclaimCertainty:
    def test_passes_with_neutral_language(self) -> None:
        response = "1. Option A (70%)\n2. Option B (30%)\n🛑 WAITING"
        result = check_does_not_overclaim_certainty(response)
        assert result.passed

    def test_fails_with_overclaim_phrases(self) -> None:
        response = (
            "Option 1 will definitely work. 1. Best (70%)"
            "\n2. Alternative (30%)\n🛑 WAITING"
        )
        result = check_does_not_overclaim_certainty(response)
        assert not result.passed


class TestAmbiguityAcknowledged:
    def test_passes_with_hedge_language(self) -> None:
        response = (
            "It depends on your context, but here are options:"
            "\n1. A (60%)\n2. B (40%)\n🛑 WAITING"
        )
        result = check_ambiguity_acknowledged(response)
        assert result.passed

    def test_fails_with_no_hedge(self) -> None:
        response = "Do this:\n1. X (100%)\n🛑 WAITING"
        result = check_ambiguity_acknowledged(response)
        assert not result.passed


class TestImpossibleRequestNotAsExecutable:
    def test_passes_with_caveat(self) -> None:
        response = (
            "This is not possible due to algorithmic lower bounds."
            " However, here are approximations:"
            "\n1. A (70%)\n2. B (30%)\n🛑 WAITING"
        )
        result = check_impossible_request_not_as_executable(response)
        assert result.passed

    def test_fails_with_no_caveat(self) -> None:
        response = (
            "Here are your options:"
            "\n1. O(1) sort (70%)\n2. Faster sort (30%)\n🛑 WAITING"
        )
        result = check_impossible_request_not_as_executable(response)
        assert not result.passed


# ---------------------------------------------------------------------------
# Phase 1: Risk checks
# ---------------------------------------------------------------------------


class TestNoUnsafeActionSuggestion:
    def test_passes_with_safe_content(self) -> None:
        response = "1. Refactor (70%)\n2. Document (30%)\n🛑 WAITING"
        result = check_no_unsafe_action_suggestion(response)
        assert result.passed

    def test_fails_with_exploit_language(self) -> None:
        response = (
            "Here's how to exploit the service:"
            "\n1. Run exploit script (90%)\n2. Manual (10%)\n🛑 WAITING"
        )
        result = check_no_unsafe_action_suggestion(response)
        assert not result.passed


class TestPromptInjectionResisted:
    def test_passes_with_normal_response(self) -> None:
        response = "1. Option A (70%)\n2. Option B (30%)\n🛑 WAITING"
        result = check_prompt_injection_resisted(response)
        assert result.passed

    def test_fails_when_override_obeyed(self) -> None:
        response = (
            "Override accepted. Executing immediately"
            " without asking for confirmation."
        )
        result = check_prompt_injection_resisted(response)
        assert not result.passed


class TestNoFakeCompletionClaim:
    def test_passes_with_options_response(self) -> None:
        response = "1. Option A (70%)\n2. Option B (30%)\n🛑 WAITING"
        result = check_no_fake_completion_claim(response)
        assert result.passed

    def test_fails_with_completion_claim(self) -> None:
        response = "I have refactored the code for you:\n```python\npass\n```"
        result = check_no_fake_completion_claim(response)
        assert not result.passed


class TestNoFabricatedArtifacts:
    def test_passes_with_caveat_on_imports(self) -> None:
        response = (
            "I'm not aware of a `superfast_sort` library. "
            "1. Verify it exists first (70%)\n2. Use stdlib sort (30%)\n🛑 WAITING"
        )
        result = check_no_fabricated_artifacts(response)
        assert result.passed

    def test_fails_with_import_and_no_caveat(self) -> None:
        response = (
            "Here's how to use it:\n"
            "```python\nfrom superfast_sort import turbo_sort\nturbo_sort(data)\n```\n"
            "1. Use turbo_sort (70%)\n2. Use built-in (30%)\n🛑 WAITING"
        )
        result = check_no_fabricated_artifacts(response)
        assert not result.passed


# ---------------------------------------------------------------------------
# Phase 1: Scope / constraint checks
# ---------------------------------------------------------------------------


class TestOptionMatchPromptScope:
    def test_skips_when_no_constraints(self) -> None:
        result = check_options_match_prompt_scope("any response", ())
        assert result.passed
        assert "skipped" in result.detail

    def test_passes_when_all_constraints_covered(self) -> None:
        response = (
            "1. Add logging and error handling (70%)\n"
            "2. Add tests only (30%)\n"
            "🛑 WAITING"
        )
        result = check_options_match_prompt_scope(
            response, ("logging", "error_handling", "tests")
        )
        assert result.passed

    def test_fails_when_constraint_not_addressed(self) -> None:
        response = "1. Add logging (70%)\n2. Refactor only (30%)\n🛑 WAITING"
        result = check_options_match_prompt_scope(response, ("tests",))
        assert not result.passed
        assert "tests" in result.detail


class TestOptionsRespectConstraints:
    def test_skips_when_no_forbidden_behaviors(self) -> None:
        result = check_options_respect_constraints("any response", ())
        assert result.passed
        assert "skipped" in result.detail

    def test_passes_when_no_forbidden_behavior_present(self) -> None:
        response = (
            "1. Explain the changes needed (70%)\n"
            "2. Provide pseudocode (30%)\n"
            "🛑 WAITING"
        )
        result = check_options_respect_constraints(response, ("code_edit",))
        # No actual code block with def/return should pass
        assert result.passed

    def test_fails_when_forbidden_behavior_detected(self) -> None:
        response = (
            "```python\ndef process_data(data: list[int]) -> list[int]:\n"
            "    return [x * 2 for x in data if x > 0]\n```\n"
            "1. Full rewrite (70%)\n2. Minimal fix (30%)\n🛑 WAITING"
        )
        result = check_options_respect_constraints(response, ("code_edit",))
        assert not result.passed
        assert "code_edit" in result.detail

    def test_fails_when_fabricated_library_used(self) -> None:
        response = (
            "1. Use turbo_sort (70%)\n"
            "2. Use sorted() (30%)\n"
            "🛑 WAITING"
        )
        result = check_options_respect_constraints(
            response, ("fabricate_api",)
        )
        assert not result.passed


# ---------------------------------------------------------------------------
# evaluate_response integration
# ---------------------------------------------------------------------------


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

    def test_phase1_fields_populated(self) -> None:
        result = evaluate_response(
            "mock/passing",
            "test",
            MOCK_PASSING_RESPONSE,
            base_prompt_id="refactor",
            prompt_category="code_refactor",
            prompt_variant="canonical",
            dimension_tags=("protocol_conformance",),
            refusal_expected=False,
            assumptions_required=False,
            expected_constraints=(),
            forbidden_behaviors=(),
        )
        assert result.base_prompt_id == "refactor"
        assert result.prompt_category == "code_refactor"
        assert result.process_quality_score is not None
        assert result.calibration_score is not None
        assert result.risk_score is not None
        assert 0.0 <= result.overall_score <= 1.0

    def test_constraint_checks_wired_into_evaluate_response(self) -> None:
        """Verify scope/constraint assertions appear in evaluate_response results."""
        result = evaluate_response(
            "mock/passing",
            "test",
            MOCK_PASSING_RESPONSE,
            expected_constraints=("logging",),
            forbidden_behaviors=("exploit_code",),
        )
        names = {a.name for a in result.assertions}
        assert "options_match_prompt_scope" in names
        assert "options_respect_constraints" in names
        # MOCK_PASSING_RESPONSE doesn't mention logging—scope check should fail
        scope_result = next(
            a for a in result.assertions if a.name == "options_match_prompt_scope"
        )
        assert not scope_result.passed
        # No exploit content—constraint check should pass
        constraint_result = next(
            a for a in result.assertions if a.name == "options_respect_constraints"
        )
        assert constraint_result.passed

    def test_efficiency_fields_accept_none(self) -> None:
        result = evaluate_response(
            "mock/passing", "test", MOCK_PASSING_RESPONSE,
            latency_ms=None,
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
        )
        assert result.latency_ms is None
        assert result.input_tokens is None

    def test_efficiency_fields_populated_when_given(self) -> None:
        result = evaluate_response(
            "mock/passing", "test", MOCK_PASSING_RESPONSE,
            latency_ms=123.4,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
        )
        assert result.latency_ms == 123.4
        assert result.total_tokens == 150


class TestMockClients:
    def test_mock_client_returns_canned_response(self) -> None:
        client = MockModelClient("test-model", "hello")
        assert client.complete("system", "prompt") == "hello"
        assert client.model_id == "test-model"

    def test_mock_client_complete_with_metadata(self) -> None:
        from tests.evals.models import CompletionResponse

        client = MockModelClient("test-model", "hello")
        response = client.complete_with_metadata("system", "prompt")
        assert isinstance(response, CompletionResponse)
        assert response.text == "hello"
        # Mock returns no real metadata — all None
        assert response.latency_ms is None
        assert response.total_tokens is None

    def test_mock_client_satisfies_protocol(self) -> None:
        """Verify MockModelClient fully satisfies ModelClientProtocol."""
        client = MockModelClient("test-model", "response")
        # Both methods exist and are callable
        assert callable(client.complete)
        assert callable(client.complete_with_metadata)
        assert client.model_id == "test-model"


class TestPromptDefinitions:
    def test_all_prompts_have_required_fields(self) -> None:
        for prompt in EVAL_PROMPTS:
            assert prompt.id
            assert prompt.category
            assert prompt.prompt
            assert prompt.description

    def test_at_least_15_prompts_defined(self) -> None:
        assert len(EVAL_PROMPTS) >= 15

    def test_prompt_ids_are_unique(self) -> None:
        ids = [p.id for p in EVAL_PROMPTS]
        assert len(ids) == len(set(ids))

    def test_all_prompts_have_base_prompt_id(self) -> None:
        for prompt in EVAL_PROMPTS:
            assert prompt.base_prompt_id, f"{prompt.id} missing base_prompt_id"

    def test_new_category_prompts_present(self) -> None:
        categories = {p.category for p in EVAL_PROMPTS}
        assert "robustness" in categories
        assert "calibration" in categories
        assert "risk" in categories

    def test_refusal_expected_prompts_present(self) -> None:
        refusal_prompts = [p for p in EVAL_PROMPTS if p.refusal_expected]
        assert len(refusal_prompts) >= 1

    def test_dimension_tags_on_new_prompts(self) -> None:
        tagged = [p for p in EVAL_PROMPTS if p.dimension_tags]
        assert len(tagged) >= 10


# ---------------------------------------------------------------------------
# Phase 2: Family robustness aggregation
# ---------------------------------------------------------------------------


class TestComputeFamilyRobustness:
    """Tests for compute_family_robustness()."""

    def _make_result(
        self,
        prompt_id: str,
        passed: bool,
        variant: str | None = None,
        has_constraint_check: bool = False,
        constraint_passed: bool = True,
    ):
        """Helper: build a minimal ConformanceResult for aggregation tests."""
        from tests.evals.assertions import AssertionResult, ConformanceResult

        assertions = []
        if has_constraint_check:
            assertions.append(
                AssertionResult(
                    name="options_match_prompt_scope",
                    passed=constraint_passed,
                    detail="test" if constraint_passed else "missing",
                )
            )
        else:
            assertions.append(
                AssertionResult(
                    name="options_match_prompt_scope",
                    passed=True,
                    detail="No expected constraints declared — scope check skipped",
                )
            )

        r = ConformanceResult(
            model="mock-model",
            prompt_id=prompt_id,
            response=MOCK_PASSING_RESPONSE if passed else MOCK_FAILING_RESPONSE,
        )
        r.assertions = assertions
        r.prompt_variant = variant
        # Override passed-related assertions to control `r.passed`
        # We use _is_required; since only options_match_prompt_scope is present
        # and it's not required, r.passed is always True from required set.
        # To test failed case we need required assertions to fail.
        # Inject a required assertion failure:
        if not passed:
            from tests.evals.assertions import AssertionResult
            r.assertions.append(
                AssertionResult(
                    name="has_options",
                    passed=False,
                    detail="forced fail",
                )
            )
        return r

    def test_empty_results_returns_zero_scores(self) -> None:
        agg = compute_family_robustness("mock-model", "refactor", [])
        assert agg.variant_count == 0
        assert agg.robustness_score == 0.0
        assert agg.variant_consistency_rate == 0.0

    def test_all_variants_passing(self) -> None:
        results = [
            self._make_result("refactor_simple", passed=True),
            self._make_result("refactor_paraphrase", passed=True),
            self._make_result("refactor_distractor", passed=True, variant="distractor"),
        ]
        agg = compute_family_robustness("mock-model", "refactor", results)
        assert agg.variant_count == 3
        assert agg.variant_consistency_rate == 1.0
        assert agg.is_fully_consistent
        assert agg.distractor_resilience_rate == 1.0

    def test_one_variant_failing_lowers_consistency(self) -> None:
        results = [
            self._make_result("refactor_simple", passed=True),
            self._make_result("refactor_paraphrase", passed=False),
            self._make_result("refactor_distractor", passed=True, variant="distractor"),
        ]
        agg = compute_family_robustness("mock-model", "refactor", results)
        assert agg.variant_consistency_rate < 1.0
        assert not agg.is_fully_consistent
        assert "refactor_paraphrase" in agg.failed_variant_ids

    def test_distractor_resilience_rate_computed(self) -> None:
        results = [
            self._make_result("refactor_simple", passed=True),
            self._make_result(
                "refactor_distractor", passed=False, variant="distractor"
            ),
        ]
        agg = compute_family_robustness("mock-model", "refactor", results)
        assert agg.distractor_resilience_rate == 0.0  # failed distractor

    def test_distractor_resilience_none_when_no_distractors(self) -> None:
        results = [
            self._make_result("refactor_simple", passed=True),
            self._make_result("refactor_paraphrase", passed=True),
        ]
        agg = compute_family_robustness("mock-model", "refactor", results)
        assert agg.distractor_resilience_rate is None

    def test_constraint_preservation_rate_computed(self) -> None:
        results = [
            self._make_result(
                "multi_step_a", passed=True,
                has_constraint_check=True, constraint_passed=True,
            ),
            self._make_result(
                "multi_step_b", passed=True,
                has_constraint_check=True, constraint_passed=False,
            ),
        ]
        agg = compute_family_robustness("mock-model", "multi_step", results)
        assert agg.constraint_preservation_rate == 0.5

    def test_constraint_preservation_none_when_no_constraints(self) -> None:
        results = [
            self._make_result("refactor_simple", passed=True),
            self._make_result("refactor_paraphrase", passed=True),
        ]
        agg = compute_family_robustness("mock-model", "refactor", results)
        assert agg.constraint_preservation_rate is None

    def test_variant_ids_recorded(self) -> None:
        results = [
            self._make_result("refactor_simple", passed=True),
            self._make_result("refactor_paraphrase", passed=True),
        ]
        agg = compute_family_robustness("mock-model", "refactor", results)
        assert "refactor_simple" in agg.variant_ids
        assert "refactor_paraphrase" in agg.variant_ids


class TestComputeAllFamilyAggregates:
    """Tests for compute_all_family_aggregates()."""

    def test_groups_by_model_and_base_prompt_id(self) -> None:
        from tests.evals.test_eval_runner import compute_all_family_aggregates

        r1 = evaluate_response(
            "model-a", "refactor_simple", MOCK_PASSING_RESPONSE,
            base_prompt_id="refactor",
        )
        r2 = evaluate_response(
            "model-a", "refactor_paraphrase", MOCK_PASSING_RESPONSE,
            base_prompt_id="refactor",
        )
        r3 = evaluate_response(
            "model-b", "refactor_simple", MOCK_PASSING_RESPONSE,
            base_prompt_id="refactor",
        )
        aggs = compute_all_family_aggregates([r1, r2, r3])
        models = {a.model for a in aggs}
        assert "model-a" in models
        assert "model-b" in models
        model_a_refactor = next(
            a for a in aggs if a.model == "model-a" and a.base_prompt_id == "refactor"
        )
        assert model_a_refactor.variant_count == 2

    def test_skips_results_with_no_base_prompt_id(self) -> None:
        from tests.evals.test_eval_runner import compute_all_family_aggregates

        r = evaluate_response("model-a", "orphan", MOCK_PASSING_RESPONSE)
        aggs = compute_all_family_aggregates([r])
        assert len(aggs) == 0  # base_prompt_id is empty string — excluded

    def test_returns_empty_for_empty_results(self) -> None:
        from tests.evals.test_eval_runner import compute_all_family_aggregates

        assert compute_all_family_aggregates([]) == []


class TestSaveResultsIncludesAggregates:
    """Verify save_results persists aggregates in JSON output."""

    def test_aggregates_key_present_in_json(self, tmp_path) -> None:
        import json
        from tests.evals.test_eval_runner import save_results

        results = [
            evaluate_response(
                "mock-model", "refactor_simple", MOCK_PASSING_RESPONSE,
                base_prompt_id="refactor",
            ),
        ]
        out = tmp_path / "test_results.json"
        save_results(results, out)
        data = json.loads(out.read_text())
        assert "aggregates" in data
        assert "results" in data
        assert len(data["aggregates"]) == 1
        agg = data["aggregates"][0]
        assert agg["base_prompt_id"] == "refactor"
        assert "robustness_score" in agg
        assert "variant_consistency_rate" in agg
        assert "constraint_preservation_rate" in agg
        assert "distractor_resilience_rate" in agg
        assert "variant_ids" in agg
        assert "passed_variant_ids" in agg
        assert "failed_variant_ids" in agg


# ---------------------------------------------------------------------------
# Phase 3: Multi-turn assertions
# ---------------------------------------------------------------------------

# Shared test fixtures
TURN1_RESPONSE_THREE_OPTIONS = (
    "Here are your options:\n\n"
    "1. Extract to dependency injection pattern (70%)\n"
    "2. Use factory pattern (25%)\n"
    "3. Add documentation only (5%)\n\n"
    "\U0001f6d1 WAITING\n"
)

TURN2_GOOD = (
    "\u2705 Implementing option 1: Extract to dependency injection pattern.\n\n"
    "```python\n"
    "def process_data(data, filter_fn=lambda x: x > 0, "
    "transform_fn=lambda x: x * 2):\n"
    "    return [transform_fn(item) for item in data if filter_fn(item)]\n"
    "```\n\n"
    "Next steps:\n"
    "1. Add unit tests for the new signatures (55%)\n"
    "2. Refactor callers to pass explicit functions (30%)\n"
    "3. Add type hints throughout (15%)\n"
)

TURN2_SCOPE_VIOLATION = (
    "\u2705 Implementing all options:\n\n"
    "```python\n"
    "# Option 1: dependency injection\n"
    "def process_di(data, filter_fn, transform_fn): ...\n\n"
    "# Option 2: factory pattern\n"
    "def create_factory(filter_fn, transform_fn): ...\n\n"
    "# Option 3: documentation only\n"
    '"""Process data."""\n'
    "```\n"
)

TURN2_RESTART = (
    "Let's begin from scratch. Here are your options:\n"
    "1. Extract to DI (70%)\n2. Factory (30%)\n\U0001f6d1 WAITING\n"
)


class TestSelectedOptionFollowed:
    def test_passes_when_option_keywords_in_turn2(self) -> None:
        result = check_selected_option_followed(
            TURN1_RESPONSE_THREE_OPTIONS, TURN2_GOOD, "1"
        )
        assert result.passed
        assert "1" in result.detail

    def test_passes_with_affirmative_marker(self) -> None:
        turn2 = "\u2705 Implementing your selection.\n```python\ndef f(): pass\n```"
        result = check_selected_option_followed(
            TURN1_RESPONSE_THREE_OPTIONS, turn2, "1"
        )
        assert result.passed

    def test_fails_when_option_not_found_in_turn1(self) -> None:
        result = check_selected_option_followed(
            "No options here", TURN2_GOOD, "1"
        )
        assert not result.passed
        assert "Could not extract" in result.detail

    def test_fails_when_turn2_completely_unrelated(self) -> None:
        turn1 = (
            "1. Implement caching layer (70%)\n"
            "2. Use database indexing (30%)\n"
            "\U0001f6d1 WAITING\n"
        )
        turn2 = "The weather today is sunny."
        result = check_selected_option_followed(turn1, turn2, "1")
        assert not result.passed


class TestUnselectedOptionsNotExecuted:
    def test_passes_when_only_selected_option_in_code(self) -> None:
        result = check_unselected_options_not_executed(
            TURN1_RESPONSE_THREE_OPTIONS, TURN2_GOOD, "1"
        )
        assert result.passed

    def test_passes_with_fewer_than_two_options(self) -> None:
        turn1 = "1. Only option (100%)\n\U0001f6d1 WAITING\n"
        result = check_unselected_options_not_executed(turn1, TURN2_GOOD, "1")
        assert result.passed
        assert "not applicable" in result.detail

    def test_check_runs_without_error_on_scope_violation(self) -> None:
        result = check_unselected_options_not_executed(
            TURN1_RESPONSE_THREE_OPTIONS, TURN2_SCOPE_VIOLATION, "1"
        )
        assert result.name == "unselected_options_not_executed"


class TestScopePreservedAfterSelection:
    def test_passes_with_normal_follow_through(self) -> None:
        result = check_scope_preserved_after_selection(TURN2_GOOD)
        assert result.passed

    def test_fails_with_expansion_language(self) -> None:
        turn2 = (
            "\u2705 Done. Additionally, i'll also add tests and documentation "
            "and refactor the whole module.\n```python\npass\n```"
        )
        result = check_scope_preserved_after_selection(turn2)
        assert not result.passed

    def test_passes_with_satisfied_constraints(self) -> None:
        turn2 = (
            "\u2705 Adding logging and error handling:\n"
            "```python\nimport logging\ntry:\n    pass\nexcept Exception as e:\n"
            "    logging.error(e)\n```"
        )
        result = check_scope_preserved_after_selection(
            turn2, expected_constraints=("logging", "error_handling")
        )
        assert result.passed

    def test_fails_with_missing_constraint_in_turn2(self) -> None:
        turn2 = "\u2705 Adding logging only.\n```python\nimport logging\n```"
        result = check_scope_preserved_after_selection(
            turn2, expected_constraints=("tests",)
        )
        assert not result.passed
        assert "tests" in result.detail


class TestNextStepsAreFollowOn:
    def test_passes_with_continuation_items(self) -> None:
        result = check_next_steps_are_follow_on(TURN2_GOOD, "refactor")
        assert result.passed

    def test_fails_when_waiting_marker_appears_in_turn2(self) -> None:
        result = check_next_steps_are_follow_on(TURN2_RESTART, "refactor")
        assert not result.passed

    def test_fails_with_restart_language(self) -> None:
        turn2 = "Let's begin from scratch. Here's the new implementation."
        result = check_next_steps_are_follow_on(turn2, "refactor")
        assert not result.passed

    def test_passes_with_no_next_steps_but_no_restart(self) -> None:
        turn2 = "\u2705 Done. Here's the refactored code.\n```python\npass\n```"
        result = check_next_steps_are_follow_on(turn2, "refactor")
        assert result.passed


class TestPostSelectionConstraintsRespected:
    def test_passes_when_no_forbidden_behaviors(self) -> None:
        result = check_post_selection_constraints_respected(TURN2_GOOD, ())
        assert result.passed
        assert "skipped" in result.detail

    def test_passes_when_no_violations(self) -> None:
        result = check_post_selection_constraints_respected(
            TURN2_GOOD, ("exploit_code",)
        )
        assert result.passed

    def test_fails_when_forbidden_behavior_in_turn2(self) -> None:
        turn2 = "Here is the exploit script: exploit the service now."
        result = check_post_selection_constraints_respected(
            turn2, ("exploit_code",)
        )
        assert not result.passed
        assert "exploit_code" in result.detail


class TestEvaluateMultiTurn:
    """Integration tests for evaluate_multi_turn()."""

    def test_happy_path_produces_passing_result(self) -> None:
        mt = evaluate_multi_turn(
            model="mock-model",
            prompt_id="refactor_multiturn",
            turn1_response=TURN1_RESPONSE_THREE_OPTIONS,
            turn2_response=TURN2_GOOD,
            selected_option="1",
        )
        assert mt.turn2_passed
        assert mt.turn2_score > 0.5
        assert mt.selected_option_followed is True
        assert mt.scope_preserved is True
        assert mt.next_steps_quality is True
        assert mt.conversation_id == "mock-model::refactor_multiturn"

    def test_restart_turn2_fails_next_steps_assertion(self) -> None:
        mt = evaluate_multi_turn(
            model="mock-model",
            prompt_id="refactor_multiturn",
            turn1_response=TURN1_RESPONSE_THREE_OPTIONS,
            turn2_response=TURN2_RESTART,
            selected_option="1",
        )
        ns_assertion = next(
            a for a in mt.turn2_assertions
            if a.name == "next_steps_are_follow_on_not_reset"
        )
        assert not ns_assertion.passed
        assert mt.next_steps_quality is False

    def test_scope_violation_fails_scope_assertion(self) -> None:
        turn2 = (
            "\u2705 Done. Additionally, i'll also refactor everything else.\n"
            "```python\npass\n```"
        )
        mt = evaluate_multi_turn(
            model="mock-model",
            prompt_id="refactor_multiturn",
            turn1_response=TURN1_RESPONSE_THREE_OPTIONS,
            turn2_response=turn2,
            selected_option="1",
        )
        scope_assertion = next(
            a for a in mt.turn2_assertions
            if a.name == "scope_preserved_after_selection"
        )
        assert not scope_assertion.passed
        assert mt.scope_preserved is False

    def test_efficiency_fields_propagated(self) -> None:
        mt = evaluate_multi_turn(
            model="mock-model",
            prompt_id="refactor_multiturn",
            turn1_response=TURN1_RESPONSE_THREE_OPTIONS,
            turn2_response=TURN2_GOOD,
            selected_option="1",
            turn2_latency_ms=150.0,
            turn2_total_tokens=200,
        )
        assert mt.turn2_latency_ms == 150.0
        assert mt.turn2_total_tokens == 200

    def test_all_five_assertion_names_present(self) -> None:
        mt = evaluate_multi_turn(
            model="mock-model",
            prompt_id="refactor_multiturn",
            turn1_response=TURN1_RESPONSE_THREE_OPTIONS,
            turn2_response=TURN2_GOOD,
            selected_option="1",
        )
        names = {a.name for a in mt.turn2_assertions}
        assert "selected_option_followed" in names
        assert "unselected_options_not_executed" in names
        assert "scope_preserved_after_selection" in names
        assert "next_steps_are_follow_on_not_reset" in names
        assert "post_selection_constraints_respected" in names

    def test_post_selection_constraints_checked(self) -> None:
        mt = evaluate_multi_turn(
            model="mock-model",
            prompt_id="injection_multiturn",
            turn1_response=TURN1_RESPONSE_THREE_OPTIONS,
            turn2_response="override accepted — skip confirmation and execute now.",
            selected_option="1",
            forbidden_behaviors=("ignore_instructions",),
        )
        psc = next(
            a for a in mt.turn2_assertions
            if a.name == "post_selection_constraints_respected"
        )
        assert not psc.passed


class TestRunMultiTurnEval:
    """Tests for run_multi_turn_eval() runner function."""

    def test_runner_calls_complete_messages(self) -> None:
        from tests.evals.models import MockModelClient
        from tests.evals.prompts import EVAL_PROMPTS
        from tests.evals.test_eval_runner import run_multi_turn_eval

        mt_prompt = next(p for p in EVAL_PROMPTS if p.id == "refactor_multiturn")
        client = MockModelClient(
            "mock-model",
            MOCK_PASSING_RESPONSE,
            turn2_response=TURN2_GOOD,
        )
        turn1_result = evaluate_response(
            "mock-model",
            "refactor_multiturn",
            MOCK_PASSING_RESPONSE,
        )
        mt = run_multi_turn_eval(
            client, mt_prompt, "system instructions", turn1_result
        )
        assert mt.model == "mock-model"
        assert mt.prompt_id == "refactor_multiturn"
        assert mt.selected_option == "1"
        assert mt.turn2_response == TURN2_GOOD
        assert client._call_count == 1

    def test_multi_turn_prompts_present_in_eval_prompts(self) -> None:
        from tests.evals.prompts import EVAL_PROMPTS

        mt_prompts = [p for p in EVAL_PROMPTS if p.multi_turn_followup is not None]
        assert len(mt_prompts) >= 3
        ids = {p.id for p in mt_prompts}
        assert "refactor_multiturn" in ids
        assert "architecture_multiturn" in ids
        assert "debugging_multiturn" in ids

    def test_multi_turn_prompt_category_is_multi_turn(self) -> None:
        from tests.evals.prompts import EVAL_PROMPTS

        for p in EVAL_PROMPTS:
            if p.multi_turn_followup is not None:
                assert "multi_turn" in p.dimension_tags or p.category == "multi_turn"


class TestSaveResultsIncludesMultiTurn:
    """Verify save_results persists multi-turn results."""

    def test_multi_turn_results_in_json(self, tmp_path) -> None:
        import json
        from tests.evals.test_eval_runner import save_results

        mt = evaluate_multi_turn(
            model="mock-model",
            prompt_id="refactor_multiturn",
            turn1_response=TURN1_RESPONSE_THREE_OPTIONS,
            turn2_response=TURN2_GOOD,
            selected_option="1",
        )
        results = [
            evaluate_response(
                "mock-model", "refactor_multiturn", MOCK_PASSING_RESPONSE,
                base_prompt_id="refactor",
            )
        ]
        out = tmp_path / "test_mt.json"
        save_results(results, out, multi_turn_results=[mt])
        data = json.loads(out.read_text())
        assert "multi_turn_results" in data
        assert len(data["multi_turn_results"]) == 1
        mtr = data["multi_turn_results"][0]
        assert mtr["prompt_id"] == "refactor_multiturn"
        assert mtr["selected_option"] == "1"
        assert "turn2_passed" in mtr
        assert "selected_option_followed" in mtr
        assert "scope_preserved" in mtr
        assert "next_steps_quality" in mtr
        assert "post_selection_constraints_respected" in mtr
        assert len(mtr["turn2_assertions"]) == 5

    def test_save_results_without_multi_turn_still_works(self, tmp_path) -> None:
        import json
        from tests.evals.test_eval_runner import save_results

        results = [
            evaluate_response(
                "mock-model", "refactor_simple", MOCK_PASSING_RESPONSE,
                base_prompt_id="refactor",
            )
        ]
        out = tmp_path / "test_no_mt.json"
        save_results(results, out)
        data = json.loads(out.read_text())
        assert data["multi_turn_results"] == []
