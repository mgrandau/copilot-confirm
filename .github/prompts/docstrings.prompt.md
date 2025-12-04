# Source Code Docstrings

Transform `{{file}}` to EXCELLENT standard (7+/8 indicators).

## Token Optimization (MANDATORY)
- Abbreviations: w/, param, cfg, msg, obj, func, num, val
- Symbols: → (returns), ← (from), ≥, ≤, ≠, ∈
- Skip: "properly", "correctly", "successfully"
- Terse: "~5ms", "∈[0,100]", "shape=(rows,cols)"

## Required Indicators (8 total)
1. Brief (first line)
2. Detailed (>200 chars)
3. Args (if params)
4. Returns (if returns)
5. Raises
6. Examples
7. Business context (purpose, provides, enables)
8. Implementation (>300 chars total)

## Templates

### Module
```python
"""Brief. Purpose, scope.

Business: Value, problems solved.
Features: • Key capabilities • Performance
"""
```

### Class
```python
class Name:
    """Brief. Purpose, role.

    Business: Why exists.
    Attributes:
        attr (type): Purpose, ranges.
    """
```

### Function (EXCELLENT)
```python
def name(p1: T1) -> RT:
    """Brief summary → core purpose.

    Multi-sentence: role, transforms, edge cases.

    Business: Why exists, value provided.

    Args:
        p1: Purpose, range, units. Complex: {key: meaning}

    Returns:
        RT: Shape, ranges, special vals (None/NaN)

    Raises:
        ErrorType: Trigger conditions

    Examples:
        ```python
        result = name(100)
        assert result.ok
        ```

    Technical: O(n), thread-safe, ~5ms, memory 2x input.
    """
```

## Workflow
1. Identify functions needing docs (missing/incomplete docstrings)
2. Document high-priority first (public APIs, complex logic)
3. Verify 7+/8 indicators per function
4. Continue with remaining functions

## Success
- All funcs: 7+/8 indicators
- Detailed: >200 chars
- Implementation: >300 chars total
- Token optimization applied
