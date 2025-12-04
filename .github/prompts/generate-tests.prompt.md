# Generate Unit Tests

Create comprehensive unit tests for `{{file}}`.

## Guidelines

1. **Location**: Place in appropriate test directory, mirror project structure
2. **Framework**: Use existing patterns (pytest, unittest, etc.)
3. **Naming**: Follow project conventions, descriptive names
4. **Coverage**:
   - Input validation
   - Expected outputs
   - Error handling/exceptions
   - Boundary conditions
   - Edge cases

## Requirements

- Mock external dependencies appropriately
- Test normal usage + error paths
- Use descriptive method names: `test_Method_Scenario_Expected`
- Ensure resource cleanup for disposable objects
- Verify logging/side effects where relevant
- Use parameterized tests to reduce duplication

## Test Categories

```python
class TestClassName:
    """Tests for ClassName.

    Categories:
        • Init (X tests): Constructor, validation
        • Core (X tests): Main functionality
        • Errors (X tests): Exception handling
        • Edge (X tests): Boundary conditions
    """

    def test_method_valid_input_returns_expected(self):
        """Validates method w/ valid input returns expected result."""
        # Arrange
        obj = ClassName(config)

        # Act
        result = obj.method(valid_input)

        # Assert
        assert result == expected

    def test_method_invalid_input_raises_error(self):
        """Validates method w/ invalid input raises ValueError."""
        obj = ClassName(config)

        with pytest.raises(ValueError, match="expected message"):
            obj.method(invalid_input)
```

## Checklist

- [ ] All public methods covered
- [ ] Edge cases tested
- [ ] Error conditions verified
- [ ] Mocks for external deps
- [ ] Resource cleanup handled
- [ ] Parameterized where applicable
- [ ] Descriptive test names
