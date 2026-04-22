# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.2] — 2026-04-22

Doc/skill release: brings the repo-shipped OpenClaw skill in sync with the canonical instructions. No CLI or runtime behavior changes.

### Changed
- **`skill/copilot-confirm/SKILL.md`** updated to match `src/copilot_confirm/agent_files/instructions/confirmation_workflow.instructions.md` (the version that the evals validate). Anyone who installed the skill from a tagged release prior to v0.2.2 was getting the v0.1.x protocol.
- New skill content includes: assumption-disclosure rule (the eval-driven win from v0.2.0), "applies to ALL requests" critical rules, the "after 🛑 WAITING your message ENDS" rule, honest-confidence ranking note, and the full Telemetry section (config-driven, sharing `~/.copilot-confirm/config.toml` with the installed CLI; documents all four modes including `file`).
- Added a header note designating `instructions.md` as the canonical source so future edits keep the two in sync.

## [0.2.1] — 2026-04-22

Hot-fix release: cleans up CI lint failures that were red on `main` since the eval-retrofit work landed (predates v0.2.0). No runtime behavior changes.

### Fixed
- Auto-fixable ruff violations across `tests/evals/` and `src/copilot_confirm/install.py` (10 fixes via `ruff --fix`, plus a manual line-wrap in the v2 telemetry CLI handler).
- Added `per-file-ignores` for `tests/evals/**` covering `E501` (long unicode/string literals in assertion messages and model IDs), `E402` (legitimately late imports of optional providers), and `B007` (loop variables retained for documentation). These are research/test files, not production.

### Notes
- v0.2.0 itself was published with red CI; the tag is intentionally not moved. v0.2.1 is the first release where CI is fully green on the tagged commit.

## [0.2.0] — 2026-04-22

First release after the eval-driven instruction tightening and telemetry schema expansion.

### Added
- **Telemetry schema v2** (additive, fully backward-compatible). New optional fields on every log entry:
  - `assumed` — did the model state an explicit assumption before the options?
  - `framing_correction` — did the user correct the stated assumption / framing?
  - `option_modification` — did the user pick an option but modify it ("1 but skip the tests")?
  - `task_id` — short opaque id (≤8 alnum chars) linking multi-turn confirms within one task.
  See [`docs/telemetry-plan.md`](docs/telemetry-plan.md) for the full v2 spec and what each signal lets you measure (framing accuracy, option fidelity, calibration accuracy, multi-turn flow shape).
- **Telemetry config `mode = "file"`** — alias of `local` for non-CLI consumers (e.g. the OpenClaw skill that ships the same protocol into other agent harnesses without the pip package). Same wire format, same config file.
- **Pricing module** (`tests/evals/pricing.py`) — retail per-1M-token rates for the 7 currently-evaluated models; `estimated_cost` is now populated on every `ConformanceResult` and surfaced in saved JSON (was always `null` previously).
- **Cheap-only eval runner** (`tests/evals/run_cheap_only.py`) — fast A/B iteration on the 3 cheap models (haiku-4.5, gemini-3-flash, gpt-5-mini).
- **Telemetry section in README** with config schema, all four modes, v2 wire format snippet, privacy contract, and inspect/send commands.
- **`docs/journal/2026-04-22.md`** — design rationale for the assumption-disclosure tweak (why stated assumptions accelerate intent-homing better than hedge phrases).
- **`docs/evals-retrofit-plan.md`** and expanded eval coverage (`tests/evals/prompts.py`, `assertions.py`, `test_assertions.py`, `test_eval_runner.py`).

### Changed
- **Instruction tightening** (`agent_files/instructions/confirmation_workflow.instructions.md`): on ambiguous prompts the model now states the assumption it's making in one short line before the options. Clarified that options are ranked by honest confidence and that overlapping approaches are fine — what matters is the likelihood ordering.
- **`check_unselected_options_not_executed`**: subtract keywords shared across options, prompt-level keywords, and selected-option keywords; raise threshold from 2 to 3 distinctive matches. Removes false-positives on domain-saturated prompts (e.g. config/settings vocab unavoidable in any architecture answer).
- **`check_ambiguity_acknowledged`**: an explicit assumption-statement is now treated as a valid form of ambiguity acknowledgement, not just hedge phrases.

### Backward compatibility
- Legacy `--correction` flag on `copilot-confirm log` keeps working unchanged.
- When v2 fields are provided, `correction` is computed as `framing_correction OR option_modification` so emitters can't desync them.
- v1 telemetry log lines remain readable; missing v2 fields default to `no` / `-`.

### Measured impact
Full 7-model eval, 20 prompts each + 21 multi-turn:
- `assumptions_disclosed` failures: **36 → 7** (5×)
- `ambiguity_acknowledged` failures (rescored under new check): **25 → 3**
- multi-turn turn-2 pass: **21/21**, **0** unselected-option leaks
- aggregate score: **up on every model** (+0.011 to +0.034)
- pass rate: 2 models gained a pass, 2 lost one (single-prompt drift at threshold; not real regressions)
- total cost: $0.73 → $0.83 per full run (mostly opus output tokens for the new assumption line)

Tests: 213/213 green.

## [0.1.1] — 2026-01-31

Initial published version.

[0.2.2]: https://github.com/mgrandau/copilot-confirm/releases/tag/v0.2.2
[0.2.1]: https://github.com/mgrandau/copilot-confirm/releases/tag/v0.2.1
[0.2.0]: https://github.com/mgrandau/copilot-confirm/releases/tag/v0.2.0
[0.1.1]: https://github.com/mgrandau/copilot-confirm/releases/tag/v0.1.1
