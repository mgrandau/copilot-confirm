"""Verify the vendored skill telemetry copy stays byte-identical to source.

The skill at `skill/copilot-confirm/lib/copilot_confirm_telemetry/telemetry.py`
is a vendored copy of `src/copilot_confirm/telemetry.py`. They MUST stay
byte-identical so the skill's zero-install fallback uses the exact same
code path as the pip CLI.

If this test fails, run:

    pdm run sync-skill

to refresh the vendored copy, then commit both files together.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "src" / "copilot_confirm" / "telemetry.py"
VENDORED = (
    REPO_ROOT
    / "skill"
    / "copilot-confirm"
    / "lib"
    / "copilot_confirm_telemetry"
    / "telemetry.py"
)


def test_vendored_telemetry_matches_source() -> None:
    assert SOURCE.exists(), f"source not found: {SOURCE}"
    assert VENDORED.exists(), (
        f"vendored copy not found: {VENDORED}\n"
        f"Run `pdm run sync-skill` to create it."
    )

    src_bytes = SOURCE.read_bytes()
    vnd_bytes = VENDORED.read_bytes()

    assert src_bytes == vnd_bytes, (
        f"Vendored telemetry.py has drifted from source.\n"
        f"  source:   {SOURCE}\n"
        f"  vendored: {VENDORED}\n"
        f"Run `pdm run sync-skill` to refresh, then commit both files."
    )
