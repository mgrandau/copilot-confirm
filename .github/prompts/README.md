# .github/prompts

AI-readable prompt library for VS Code Copilot agent workflows.

## 1. Component Overview

| Aspect | Value |
|--------|-------|
| **Name** | prompts |
| **Type** | library (prompt templates) |
| **Responsibility** | Reusable instruction prompts for code quality tasks |
| **Format** | Markdown w/ `{{file}}` variable substitution |
| **State** | Stateless (read-only templates) |

**Entry Points**: VS Code Copilot "Use Prompt" or agent context

**Key Decisions**:
- Token-optimized: abbreviations, symbols, compact notation
- No agent mode switching (uses current selection)
- `{{file}}` placeholder for active file injection

## 2. Code Layout

```
prompts/
├── README.md                    # This file
├── architecture-doc.prompt.md   # Generate component README.md
├── code-review.prompt.md        # Expert code review w/ priorities
├── docstrings.prompt.md         # Source code docstrings (8 indicators)
├── generate-tests.prompt.md     # Create unit tests for file
└── test-docstrings.prompt.md    # Test method docstrings (11 indicators)
```

## 3. Prompt Catalog

| Prompt | Purpose | Output |
|--------|---------|--------|
| `architecture-doc` | Generate AI-readable architectural contract | `README.md` in target dir |
| `code-review` | Expert review w/ P1-P4 prioritization | Findings report |
| `docstrings` | Add EXCELLENT docstrings (7+/8 indicators) | Modified source file |
| `generate-tests` | Create comprehensive unit tests | New test file |
| `test-docstrings` | Document tests (9+/11 indicators) | Modified test file |

## 4. Prompt Details

### architecture-doc.prompt.md
- **Sections**: Overview, Layout, Public Surface, Dependencies, Invariants, Usage, AI Map, Mermaid
- **Guards**: 🔒frozen APIs, ⚠️internal symbols
- **Output**: `README.md` with neutral-theme Mermaid diagrams

### code-review.prompt.md
- **Priorities**: P1 (security) → P4 (docs)
- **Output**: Summary, findings, metrics, testability roadmap, priority matrix

### docstrings.prompt.md
- **Standard**: EXCELLENT (7+/8 indicators)
- **Indicators**: Brief, Detailed, Args, Returns, Raises, Examples, Business, Implementation
- **Token rules**: Abbreviations (w/, cfg, param), symbols (→, ∈, ≥)

### generate-tests.prompt.md
- **Coverage**: Input validation, outputs, errors, boundaries, edge cases
- **Pattern**: AAA (Arrange/Act/Assert), descriptive names

### test-docstrings.prompt.md
- **Standard**: EXCELLENT (9+/11 indicators)
- **Extra indicators**: Arrangement, Action, Assertion, Testing Principles, Comprehensive
- **Naming**: `test_Method_Scenario_Expected`

## 5. Usage

### VS Code
1. Open target file
2. Invoke Copilot Chat
3. Use prompt: `@workspace /prompt docstrings`

### Variables
- `{{file}}` → Active file path (auto-substituted)

### Conventions
- All prompts work with any agent mode
- No external dependencies
- Token-optimized for efficiency

## 6. AI-Accessibility Map

| Task | Target | Guards | Change Impact |
|------|--------|--------|---------------|
| Add new prompt | Create `*.prompt.md` | Follow naming convention | None (additive) |
| Modify indicators | `docstrings.prompt.md` / `test-docstrings.prompt.md` | Update counts | Changes quality standard |
| Add Mermaid theme | `architecture-doc.prompt.md` | Use neutral theme | None |
| Change token rules | Any prompt | Keep abbreviation list consistent | Affects output style |

### Naming Convention
- File: `<task>.prompt.md` (kebab-case)
- Must have `{{file}}` or clear target specification
