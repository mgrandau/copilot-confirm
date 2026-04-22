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

## Schema (v2)

```
date | turn | model | selected | spread | correction | waited | options | pct
     | assumed | framing_correction | option_modification | task_id
```

Example:
```
2026-04-22 | turn=1 | model=claude-sonnet-4.6 | selected=70 | spread=[70,25,5] | correction=yes | waited=yes | options=yes | pct=yes | assumed=yes | framing_correction=no | option_modification=yes | task_id=abc12345
```

### v2 fields (added 2026-04-22)

- `assumed` (yes|no) — Did the model state an explicit assumption before the options? Surfaces whether the framing-disclosure behavior we trained for is actually happening in the wild.
- `framing_correction` (yes|no) — Did the user push back on the model's stated assumption (“no, I meant the API layer”)? Distinct from option modification. Tracks how often the model's framing was wrong.
- `option_modification` (yes|no) — Did the user pick an option but modify it (“1 but skip the tests”)? Tracks how often option text needs amendment.
- `task_id` (≤8 alphanumeric chars, `-` if absent) — Short opaque id reused across confirms within one task. Lets analysis link successive confirmations into a single intent-evolution flow.

### Backward compatibility

- `correction` is retained. When v2 fields are provided, it is computed as `framing_correction OR option_modification` (legacy emitters keep working unchanged; v2 emitters can't desync the two).
- `picked_rank` is **not** stored — it is derivable from `selected` and `spread` and computed in analysis.
- Old log files (v1 lines without v2 fields) remain readable; new fields default to `no` / `-` when missing.

### What v2 enables

- **Framing accuracy:** what % of stated assumptions get corrected by the user? High `framing_correction` rate per model = the model's assumptions are off.
- **Option fidelity:** what % of picks come with modifications? High `option_modification` rate = options aren't well-scoped.
- **Calibration accuracy:** rank distribution of picks (derive from `selected` + `spread`). Lots of rank-2 picks means the model's top-pick instinct is off.
- **Multi-turn flow shape:** within a `task_id`, watch how `selected` percentages evolve and how often the user re-frames. This is the closest thing to direct intent-evolution measurement.

## Config

```toml
# ~/.copilot-confirm/config.toml
[telemetry]
mode = "local"           # off | local | file | remote
path = "~/.copilot-confirm/telemetry.log"
endpoint = ""            # URL for remote mode
```

`file` (added v2, 2026-04-22) is an alias of `local` for environments that consume
this config without running the `copilot-confirm` CLI — e.g. the SKILL.md
consumer in another agent harness. It exists so the skill and the CLI share one
config file and one set of mode names.

## Privacy Contract

- ❌ No prompt content
- ❌ No option text
- ❌ No user identifiers
- ❌ No precise timestamps (date only)
- ✅ Model name in plaintext
- ✅ Fully opt-in, disabled by default
- ✅ User can read every line before sending
