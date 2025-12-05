# Copilot Confirm

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Coverage: 100%](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)](https://github.com/mgrandau/copilot-confirm)

A behavior customization tool for GitHub Copilot that enforces a deliberate, confirmation-based workflow. Instead of Copilot acting immediately, it presents ranked options with confidence percentages and waits for your approval before executing.

## 🎯 What It Does

Copilot Confirm installs custom agent and instruction files that modify how GitHub Copilot behaves. This tool implements the concepts from [The Better Agent: Homing Intent Through Probabilistic Feedback](https://mgrandau.medium.com/the-better-agent-homing-intent-through-probabilistic-feedback-d545466ebe6d?source=friends_link&sk=5a46e536997eb087c5ced4c0cee08679).

- **Presents Options First**: Shows 2-3 ranked options with confidence percentages before taking action
- **Waits for Confirmation**: Stops and waits for your explicit approval (e.g., "1", "option 2", "DI")
- **Suggests Next Steps**: After completing a task, offers forward-looking options to keep momentum
- **Prevents Premature Actions**: Never acts without confirmation, never asks mid-task, never ends vaguely

### Example Workflow

```text
You: "Refactor this function"

Copilot: "Options:
  1. Extract to dependency injection pattern (70%)
  2. Use factory pattern (25%)
  3. Just add documentation (5%)

🛑 WAITING"

You: "1"

Copilot: ✅ [implements DI pattern]
"Next steps:
  - Add unit tests (55%)
  - Refactor related functions (30%)
  - Update documentation (15%)"
```

## 📦 Installation

### Prerequisites

- Python 3.13+
- VS Code or VS Code Insiders

### Install via pip

```bash
# Install directly from GitHub
pip install git+https://github.com/mgrandau/copilot-confirm.git

# Install globally to VS Code
copilot-confirm --global

# Or install locally to current repository
copilot-confirm --local
```

### Install from Source (Development)

```bash
# Clone the repository
git clone https://github.com/mgrandau/copilot-confirm.git
cd copilot-confirm

# Install with PDM (recommended for development)
pdm install

# Run the installer
pdm run copilot-confirm --global    # VS Code stable
pdm run copilot-confirm --local     # Current repository
```

### Installation Options

| Flag | Description |
|------|-------------|
| `--local`, `-l` | Install to `.github/` in current repository (default) |
| `--global`, `-g` | Install to VS Code user configuration directory |
| `--insiders`, `-i` | Use VS Code Insiders instead of stable (with `--global`) |
| `--dry-run`, `-n` | Preview what would be installed without copying |
| `--version`, `-V` | Show version and exit |
| `--log-level` | Set logging verbosity (DEBUG, INFO, WARNING, ERROR) |
| `--log-file` | Write logs to a file |

### What Gets Installed

**Local Install** (`.github/`):

```text
.github/
├── agents/
│   └── copilot_confirm.agent.md
└── instructions/
    └── confirmation_workflow.instructions.md
```

**Global Install** (VS Code User directory):

```text
~/.config/Code/User/prompts/           # Linux
~/Library/Application Support/Code/User/prompts/  # macOS
%APPDATA%\Code\User\prompts\           # Windows
├── copilot_confirm.agent.md
└── confirmation_workflow.instructions.md
```

## 🚀 Usage

After installation, the Copilot Confirm agent will be available in VS Code:

1. Open the Copilot Chat panel
2. Select the **Copilot_Confirm** agent from the agent dropdown
3. Start chatting - Copilot will now follow the confirmation workflow

## 🛠️ Development

```bash
# Install dev dependencies
pdm install

# Run tests
pdm run test

# Run tests with coverage
pdm run test-cov

# Lint code
pdm run lint

# Format code
pdm run format

# Security scan
pdm run security
```

## 📁 Project Structure

```text
copilot-confirm/
├── src/copilot_confirm/
│   ├── __init__.py
│   ├── __version__.py
│   ├── install.py              # CLI and installation logic
│   └── agent_files/
│       ├── agents/
│       │   └── copilot_confirm.agent.md
│       └── instructions/
│           └── confirmation_workflow.instructions.md
├── tests/
│   └── test_main.py
├── pyproject.toml
└── README.md
```

## 📐 Architecture Documentation

AI-readable architectural contracts for each component:

| Component | README | Description |
|-----------|--------|-------------|
| **copilot_confirm** | [`src/copilot_confirm/README.md`](src/copilot_confirm/README.md) | Core package: CLI, installer, path resolution, protocols |
| **prompts** | [`.github/prompts/README.md`](.github/prompts/README.md) | Prompt library: docstrings, tests, code review, architecture |

These READMEs follow a standardized format with:

- Public API surface (🔒frozen, ⚠️internal)
- Dependencies and invariants
- AI-accessibility maps for safe modifications
- Mermaid diagrams for visualization

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📬 Contact

For questions, issues, or suggestions, please [open an issue](https://github.com/mgrandau/copilot-confirm/issues) on GitHub.
