"""Pytest configuration for utilities tests."""

import sys
from pathlib import Path


def pytest_configure(config):  # noqa: ARG001
    """Add utilities directory to path for imports."""
    # Add the utilities directory (where create_issues.py lives)
    utilities_dir = Path(__file__).parent.parent.parent / "utilities"
    if str(utilities_dir) not in sys.path:
        sys.path.insert(0, str(utilities_dir))


def pytest_collection_modifyitems(session, config, items):  # noqa: ARG001
    """Filter out functions from create_issues.py that aren't tests."""
    # These are actual utility functions, not tests
    exclude_functions = {
        "test_github_cli_available",
        "test_input_safety",
    }

    items[:] = [
        item
        for item in items
        if not (
            hasattr(item, "name")
            and item.name in exclude_functions
            and "create_issues.py" in str(item.fspath)
        )
    ]
