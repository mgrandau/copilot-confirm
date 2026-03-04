---
applyTo: '**'
---

# Project Intent & Design

This project follows the [Human-AI Intent Transfer Principles](https://mgrandau.medium.com/human-ai-intent-transfer-principles-b6e7404e3d26?source=friends_link&sk=858917bd3f4a686974ed6b6c9c059ac8) — the confirmation workflow IS the intent transfer mechanism.

**Context chain (read in order when making design decisions):**

1. [🧭 Intent](../../README.md#-intent) — project philosophy: the gap between intent and action is where mistakes happen
2. [PROJECT_PLAN.md](../../docs/PROJECT_PLAN.md) — phase goals, risk posture, issue history
3. [Architecture](../../src/copilot_confirm/README.md) — component map, invariants, DI contracts, AI-accessibility map
4. Source code — the implementation

**Core design values:**

- **Zero runtime dependencies** — stdlib only, no pip installs needed beyond the package itself
- **Protocol-based DI** — testability without mocks, `FileSystemProtocol` / `EnvironmentProtocol`
- **Agent ≠ instruction** — the agent file defines the persona, the instruction file defines the workflow. Separate concerns.
- **Frozen results** — `InstallationResult` and `FileMapping` are immutable. Downstream can't mutate install state.
- **Minimal effective instructions** — the confirmation workflow is ~15 lines. Verbose instructions get ignored by LLMs.
- **Quality before shipping** — 12 code review issues filed and resolved in Phase 1 before any user touched it

# Development Instructions for copilot-confirm

## Release Process

### Version Badge

The README badge auto-updates from GitHub releases — no manual badge edits needed.

### Release Steps

1. Update `__version__` and `__version_date__` in `src/copilot_confirm/__version__.py`
2. Commit changes: `git commit -am "release: bump version to X.X.X"`
3. Create and push tag: `git tag vX.X.X && git push origin vX.X.X`
4. Create GitHub release with **changelog notes** covering:
   - **Bug Fixes** — issues fixed with brief description
   - **Features** — new functionality added
   - **Documentation** — significant doc improvements
   - Link to full changelog comparison: `https://github.com/mgrandau/copilot-confirm/compare/vPREV...vX.X.X`

### Changelog Requirements

- Every release **must** have human-written changelog notes — do not rely solely on `--generate-notes`
- Reference issue numbers (e.g., "Fixed #16: sync confirmation workflow")
- Keep notes concise but meaningful — someone reading them should understand what changed and why

### Notes

- Tags must match pattern `vX.X.X` (e.g., `v0.1.1`)
- Badge updates within minutes of release creation

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
