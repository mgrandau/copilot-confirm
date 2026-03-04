# Project Plan — copilot-confirm

This is a **historical record** of what was actually built, when, and why. For the philosophy and design intent behind this project, see [🧭 Intent](../README.md#-intent) in the README.

Current state: **v0.1.1** — 36 tests, 100% coverage, zero runtime dependencies.

---

## Phase 1: Foundation (2025-12-04)

**Goal:** Build a working installer that puts confirmation workflow instructions where Copilot can find them — local and global.

Built the entire project in a single day: installer, tests, CI, issues (#1–#12), and architecture documentation.

| Work | Issues |
| ---- | ------ |
| Initial installer with Protocol-based DI, frozen dataclasses | — |
| Comprehensive unit tests (36 tests, 100% coverage) | — |
| CI workflow, VS Code config, PDM setup | — |
| GitHub issue creator utility for code review findings | — |
| Code review fixes: return int from main, version import, editor validation, constant extraction, docstrings, files_failed field | #1–#12 |

**Issues resolved:** #1 (main returns int), #2 (version import), #3 (editor validation), #4 (default editor constant), #5 (file path dedup), #6–#7 (docstrings), #8 (log level validation), #9 (files_failed field), #10 (editor constants), #11–#12 (docstrings)

**Key decisions:**

- Protocol-based DI from day one — same pattern as copilot-journal, prioritizes testability without mocks
- Agent file + instruction file as separate concerns — the agent defines the persona, the instruction defines the workflow
- Frozen dataclasses for `InstallationResult` and `FileMapping` — immutable results prevent downstream mutation
- All 12 code review issues filed and resolved in the same session — drove quality before shipping

**Risk posture:** Low — single developer, new project, no users. All code review issues resolved same day rather than left as tech debt.

**Design discussions (journal):**

- [2025-12-04](journal/2025-12-04.md) — Origin story: why Copilot needed a pause, two-file split (agent ≠ instruction), confidence percentages as forced ranking, installer pattern that became the template for copilot-journal. Retroactive entry — written after the principles were defined, documenting the decisions that led to them.

---

## Phase 2: Polish & Stability (2026-01-21 → 2026-01-31)

**Goal:** Stabilize the project for real-world use — refine the confirmation workflow, formalize the release process, and make installation reliable.

**Intent evolution:** The confirmation workflow instructions were cut from ~45 lines to ~15. The original had detailed examples, edge case handling, and guidance for ambiguous responses. Real usage showed that LLMs follow short structured instructions more reliably than long prose — more words about *how* to wait don't make an LLM wait better. The intent didn't change (pause before acting), but the expression of that intent was radically simplified.

Focused on workflow clarity and release engineering.

| Date | Work | Issues |
| ---- | ---- | ------ |
| 2026-01-21 | Feature enhancements, .gitignore cleanup | — |
| 2026-01-26 | CI badge, README badges, development instructions, badge conventions | — |
| 2026-01-31 | Clarified confirmation workflow instructions, bumped to v0.1.1 | #16 |

**Issues resolved:** #16 (sync confirmation workflow instructions)

**Key decisions:**

- Confirmation workflow instructions compressed to minimal effective form — the original was verbose; the current version is ~15 lines that capture the full protocol
- Badge conventions formalized (order: version → CI → Python → mypy → bandit → license → ruff) and documented in development instructions
- Development instructions created in `.github/instructions/` for AI agent alignment

**Risk posture:** Medium — preparing for others to use. The confirmation workflow is the entire value proposition — if the instructions are unclear or too verbose, Copilot ignores them or follows them inconsistently.

---

## Phase 3: Ecosystem Integration (2026-02-18 → 2026-02-20)

**Goal:** Make the confirmation workflow available beyond VS Code — OpenClaw agents and community access.

Extended reach without changing core functionality.

| Date | Work |
| ---- | ---- |
| 2026-02-18 | OpenClaw skill definition |
| 2026-02-20 | Discord community link |

**Key decisions:**

- OpenClaw skill wraps the same confirmation workflow for non-VS Code agents — one workflow, multiple surfaces
- No code changes in Phase 3 — the installer and workflow are stable, only distribution expanded

**Risk posture:** Low — additive only. No core changes, just new surfaces for existing functionality.

---

## Version History

| Version | Date | Highlights |
| ------- | ---- | ---------- |
| v0.1.0 | 2025-12-04 | Initial release — installer, 36 tests, 100% coverage, 12 issues resolved |
| **v0.1.1** | **2026-01-31** | **Refined confirmation workflow, development instructions, badge conventions** |

---

## Roadmap

| Issue | Description | Status |
| ----- | ----------- | ------ |
| [#17](https://github.com/mgrandau/copilot-confirm/issues/17) | Package as standalone executable | open |
