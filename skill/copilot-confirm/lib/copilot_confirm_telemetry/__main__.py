"""Slim CLI for the vendored skill telemetry bundle.

Implements only the runtime-facing subcommands the skill needs:

    python -m copilot_confirm_telemetry log --model ... --selected ... ...
    python -m copilot_confirm_telemetry telemetry show
    python -m copilot_confirm_telemetry telemetry send

Behavior matches `copilot-confirm log` / `copilot-confirm telemetry ...`
from the pip package exactly (same TelemetryEntry, same TelemetryLogger,
same config file at ~/.copilot-confirm/config.toml). This is the
zero-install fallback when the pip CLI is not on PATH.
"""

from __future__ import annotations

import argparse
import sys

from .telemetry import TelemetryEntry, create_telemetry_logger


def _cmd_log(args: argparse.Namespace) -> int:
    try:
        spread = [int(p.strip()) for p in args.spread.split(",") if p.strip()]
    except ValueError:
        print(
            f"❌ Error: --spread must be comma-separated integers, got: {args.spread}"
        )
        return 1

    assumed = (getattr(args, "assumed", None) or "no").lower() == "yes"
    framing_correction = (
        getattr(args, "framing_correction", None) or "no"
    ).lower() == "yes"
    option_modification = (
        getattr(args, "option_modification", None) or "no"
    ).lower() == "yes"
    task_id = getattr(args, "task_id", None) or ""
    task_id = "".join(c for c in task_id if c.isalnum() or c in "-_")[:16]

    if framing_correction or option_modification:
        correction = framing_correction or option_modification
    else:
        correction = args.correction.lower() == "yes"

    entry = TelemetryEntry(
        model=args.model,
        selected=args.selected,
        spread=spread,
        correction=correction,
        waited=args.waited.lower() == "yes",
        options=args.options.lower() == "yes",
        pct=args.pct.lower() == "yes",
        assumed=assumed,
        framing_correction=framing_correction,
        option_modification=option_modification,
        task_id=task_id,
    )

    logger_telem = create_telemetry_logger()
    line = logger_telem.log(entry)

    if line is None:
        # Mode is off — silently succeed so instructions don't fail
        return 0

    print(line)
    return 0


def _cmd_telemetry_show(_args: argparse.Namespace) -> int:
    telem = create_telemetry_logger()
    content = telem.show()
    if not content.strip():
        print("(no telemetry data)")
    else:
        print(content, end="")
    return 0


def _cmd_telemetry_send(_args: argparse.Namespace) -> int:
    telem = create_telemetry_logger()
    success, message = telem.send()
    print(message)
    return 0 if success else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="copilot_confirm_telemetry",
        description=(
            "Vendored telemetry CLI for the copilot-confirm OpenClaw skill. "
            "Subset of the `copilot-confirm` pip CLI: only `log`, "
            "`telemetry show`, `telemetry send`."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    # log
    log_parser = subparsers.add_parser(
        "log", help="Append one telemetry line"
    )
    log_parser.add_argument("--model", required=True, help="Model identifier")
    log_parser.add_argument(
        "--selected",
        required=True,
        type=int,
        help="Confidence %% of selected option (0=rejected)",
    )
    log_parser.add_argument(
        "--spread",
        required=True,
        help="Comma-separated confidence %% list (e.g. 70,25,5)",
    )
    log_parser.add_argument(
        "--correction",
        required=True,
        choices=["yes", "no"],
        help="Did user modify/redirect after selection?",
    )
    log_parser.add_argument(
        "--waited",
        required=True,
        choices=["yes", "no"],
        help="Did model stop after 🛑 WAITING?",
    )
    log_parser.add_argument(
        "--options",
        required=True,
        choices=["yes", "no"],
        help="Were numbered options presented?",
    )
    log_parser.add_argument(
        "--pct",
        required=True,
        choices=["yes", "no"],
        help="Were percentages included?",
    )
    log_parser.add_argument(
        "--assumed",
        choices=["yes", "no"],
        default="no",
        help="Did the model state an explicit assumption before the options?",
    )
    log_parser.add_argument(
        "--framing-correction",
        dest="framing_correction",
        choices=["yes", "no"],
        default="no",
        help="Did the user correct the model's framing/assumption?",
    )
    log_parser.add_argument(
        "--option-modification",
        dest="option_modification",
        choices=["yes", "no"],
        default="no",
        help="Did the user modify the chosen option in place?",
    )
    log_parser.add_argument(
        "--task-id",
        dest="task_id",
        default="",
        help="Short opaque id grouping multi-turn confirms within one task",
    )

    # telemetry
    telem_parser = subparsers.add_parser("telemetry", help="Manage telemetry log")
    telem_sub = telem_parser.add_subparsers(dest="telemetry_command")
    telem_sub.add_parser("show", help="Display the telemetry log")
    telem_sub.add_parser("send", help="POST telemetry to configured endpoint")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "log":
        return _cmd_log(args)
    if args.command == "telemetry":
        if args.telemetry_command == "show":
            return _cmd_telemetry_show(args)
        if args.telemetry_command == "send":
            return _cmd_telemetry_send(args)
        # No subcommand given
        parser.parse_args(["telemetry", "--help"])
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
