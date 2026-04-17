"""Shared fixtures for eval tests."""

import pytest

from tests.evals.models import (
    MOCK_FAILING_RESPONSE,
    MOCK_PASSING_RESPONSE,
    MOCK_PARTIAL_RESPONSE,
    MockModelClient,
)


@pytest.fixture
def passing_client() -> MockModelClient:
    return MockModelClient("mock/passing", MOCK_PASSING_RESPONSE)


@pytest.fixture
def failing_client() -> MockModelClient:
    return MockModelClient("mock/failing", MOCK_FAILING_RESPONSE)


@pytest.fixture
def partial_client() -> MockModelClient:
    return MockModelClient("mock/partial", MOCK_PARTIAL_RESPONSE)
