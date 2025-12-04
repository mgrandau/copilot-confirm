# Test Docstrings

Transform `{{file}}` test methods to EXCELLENT standard (9+/11 indicators).

## Token Optimization (MANDATORY)
- Abbreviations: w/, param, defs, pre-, post-, cfg, msg, funcs
- Terse Args: "self: Test fixture" (not verbose)
- Condense AAA: List essentials
- Skip: "properly", "correctly", "successfully"

## Required Indicators (11 total)
1. Brief (first line)
2. Detailed (>300 chars)
3. Args
4. Returns
5. Raises
6. Examples
7. Arrangement
8. Action
9. Assertion
10. Testing Principles
11. Comprehensive (>500 chars total)

## Templates

### Test Class
```python
class TestName:
    """Brief. Test scope.

    Categories: • Init (X) • Core (X) • Errors (X)
    Strategy: Fixtures, mocks, patterns
    Total: X tests
    """
```

### Test Method (EXCELLENT)
```python
def test_Method_Scenario_Expected(self):
    """Validates X w/ Y inputs, confirms Z outcome.

    Multi-stage validation covering scenarios, edge cases.
    Tests core algorithm w/ realistic data.

    Args:
        self: Test fixture

    Returns:
        None (pytest test method)

    Raises:
        AssertionError: If criteria not met

    Testing Principles: Data correctness, type safety, boundaries

    Arrangement: Test data (param=100), mock deps, initial state
    Action: Execute method(data), capture result
    Assertion: Shape (10,100), dtype float64, range [0,1]

    Examples:
        ```python
        result = obj.method(data)
        assert result.shape == (10, 100)
        ```
    """
```

## Naming Convention
`test_Method_Scenario_Expected`
- `test_Connect_ValidConfig_EstablishesConnection`
- `test_Process_NullInput_ThrowsValueError`
- `test_Get_NotFound_ReturnsNone`

## Workflow
1. Identify test methods needing docs (missing/incomplete docstrings)
2. Document high-priority first (complex tests, integration tests)
3. Verify 9+/11 indicators per test
4. Continue with remaining tests

## Success
- All tests: 9+/11 indicators
- Detailed: >300 chars
- Comprehensive: >500 chars total
- AAA structure clear
- Token optimization applied
