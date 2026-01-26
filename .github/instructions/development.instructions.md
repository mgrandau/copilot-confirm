---
applyTo: '**'
---
# Development Instructions for copilot-confirm

## Version Management

Version is stored in `src/copilot_confirm/__version__.py`:
- `__version__` - semver string (e.g., "1.0.0")
- `__version_date__` - release date (e.g., "2026-01-26")

To release a new version:
1. Update `__version__` and `__version_date__` in `src/copilot_confirm/__version__.py`
2. Commit with message: `chore: bump version to X.Y.Z`
3. Create GitHub release with tag `vX.Y.Z`

The README badge auto-updates from GitHub release tags.

## Build & Test Commands

```bash
pdm run test        # Run tests
pdm run test-cov    # Run tests with coverage
pdm run lint        # Lint code (ruff + mypy)
pdm run format      # Format code
pdm run security    # Security scan (bandit)
```

## Badge Conventions

Follow the standard badge template: https://gist.github.com/mgrandau/6fcdc506452dfd596d851242ffee8f8a

Badge order (by user importance):
1. Version (GitHub release auto-badge)
2. CI status
3. Python version
4. Type checker (mypy)
5. Security (bandit)
6. License
7. Code style (ruff)

All badges on one line.

## Code Standards

- Python 3.13+
- Type hints required (mypy strict)
- Ruff for linting and formatting
- Bandit for security scanning
