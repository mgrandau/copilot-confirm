# Telemetry Plan — Issue #22

**Intent:** Instrument copilot-confirm with plaintext, pipe-delimited decision telemetry. Captures which option was selected, the spread, whether the model waited, and whether corrections occurred. Dual-purpose: operational tracking + research data for Intent Transfer.

**Governing principles (Human-AI Intent Transfer Principles):**
- P3: Preserve Intent Through Handoffs — telemetry tracks whether intent is preserved
- P4: Validate at Each Step — telemetry logs confirmation protocol compliance
- P7: Measure What Matters — `waited`, `correction`, `selected` are the key signals

---

## Build Checklist

### Phase 1 — Core telemetry module
- [x] Create `src/copilot_confirm/telemetry.py`
  - [x] Config parsing from `~/.copilot-confirm/config.toml` (off/local/remote)
  - [x] Config defaults (off mode, default path, no endpoint)
  - [x] `TelemetryLogger` class with Protocol-based DI
  - [x] `log_entry()` — appends one pipe-delimited line to telemetry file
  - [x] Auto-generate date (today) and turn (auto-increment per day)
  - [x] `show()` — reads and displays telemetry file
  - [x] `send()` — POSTs to configured endpoint via urllib

### Phase 2 — CLI subcommands
- [x] `copilot-confirm log` — log one telemetry entry
- [x] `copilot-confirm telemetry show` — display the log
- [x] `copilot-confirm telemetry send` — POST to endpoint
- [x] Main entry point updated to route subcommands

### Phase 3 — Instructions update
- [x] Update `confirmation_workflow.instructions.md` to include `copilot-confirm log` call
- [x] Installer bakes actual CLI path into generated instructions

### Phase 4 — Tests
- [x] Unit tests for all telemetry module functions
- [x] Tests for CLI subcommands (log, show, send)
- [x] Eval tests for `copilot-confirm log` call in model responses

### Phase 5 — Verification
- [x] `pdm run test` — all tests pass
- [x] `pdm run evals` — no regression in model conformance
- [x] Commit and push

---

## Schema (v1)

```
date | turn | model | selected | spread | correction | waited | options | pct
```

Example:
```
2026-04-17 | turn=1 | model=claude-sonnet-4.6 | selected=70 | spread=[70,25,5] | correction=no | waited=yes | options=yes | pct=yes
```

## Config

```toml
# ~/.copilot-confirm/config.toml
[telemetry]
mode = "local"           # off | local | remote
path = "~/.copilot-confirm/telemetry.log"
endpoint = ""            # URL for remote mode
```

## Privacy Contract

- ❌ No prompt content
- ❌ No option text
- ❌ No user identifiers
- ❌ No precise timestamps (date only)
- ✅ Model name in plaintext
- ✅ Fully opt-in, disabled by default
- ✅ User can read every line before sending
