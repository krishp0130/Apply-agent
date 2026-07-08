"""Local command-line interface for read-only recruiting status reports."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import TextIO

from internship_agent.status import (
    DEFAULT_FIT_THRESHOLD,
    DEFAULT_TRACKING_DIR,
    StatusSummary,
    summarize_tracking_directory,
)

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level CLI parser."""
    parser = argparse.ArgumentParser(
        prog="internship-agent",
        description="Local read-only utilities for internship tracking.",
    )
    subparsers = parser.add_subparsers(dest="command")

    status_parser = subparsers.add_parser(
        "status",
        help="Summarize local CSV tracking files.",
    )
    status_parser.add_argument(
        "--tracking-dir",
        type=Path,
        default=DEFAULT_TRACKING_DIR,
        help="Directory containing tracking CSV files.",
    )
    status_parser.add_argument(
        "--fit-threshold",
        type=int,
        default=DEFAULT_FIT_THRESHOLD,
        help="Fit score threshold used for below-threshold counts.",
    )
    status_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    status_parser.set_defaults(handler=_handle_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    return run(argv, output_stream=sys.stdout, error_stream=sys.stderr)


def run(
    argv: list[str] | None = None,
    *,
    output_stream: TextIO,
    error_stream: TextIO,
) -> int:
    """Run the CLI with injectable streams for tests."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "handler"):
        parser.print_help(file=error_stream)
        return 2

    try:
        args.handler(args, output_stream)
    except (OSError, ValueError) as exc:
        logger.exception("Failed to build status report.")
        error_stream.write(f"Error: {exc}\n")
        return 1

    return 0


def _handle_status(args: argparse.Namespace, output_stream: TextIO) -> None:
    summary = summarize_tracking_directory(
        args.tracking_dir,
        fit_threshold=args.fit_threshold,
    )
    if args.format == "json":
        output_stream.write(
            json.dumps(summary.model_dump(), indent=2, sort_keys=True),
        )
        output_stream.write("\n")
        return

    output_stream.write(format_status_text(summary))


def format_status_text(summary: StatusSummary) -> str:
    """Render a human-readable status report."""
    lines = [
        "Internship Agent Status",
        f"Tracking directory: {summary.tracking_dir}",
        "",
        "Rows:",
        (
            "- roles: "
            f"{summary.roles_total} "
            f"(scored: {summary.roles_scored}, "
            f"unscored: {summary.roles_unscored}, "
            f"below threshold: {summary.roles_below_threshold})"
        ),
        f"- contacts: {summary.contacts_total}",
        (
            "- outreach drafts: "
            f"{summary.outreach_drafts_total}"
            f"{_format_counts(summary.outreach_draft_status_counts)}"
        ),
        (
            "- approvals: "
            f"{summary.approvals_total} "
            f"(requested: {summary.approvals_requested}, "
            f"approved: {summary.approvals_approved}, "
            f"rejected: {summary.approvals_rejected})"
        ),
        (
            "- application events: "
            f"{summary.application_events_total}"
            f"{_format_counts(summary.application_status_counts)}"
        ),
    ]

    if summary.application_event_type_counts:
        lines.extend(
            [
                "",
                "Application event types:",
                *[
                    f"- {name}: {count}"
                    for name, count in summary.application_event_type_counts.items()
                ],
            ],
        )

    if summary.missing_files:
        lines.extend(
            [
                "",
                "Missing tracking files:",
                *[f"- {name}" for name in summary.missing_files],
            ],
        )

    return "\n".join(lines) + "\n"


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return ""
    rendered = ", ".join(f"{name}: {count}" for name, count in counts.items())
    return f" ({rendered})"


if __name__ == "__main__":
    raise SystemExit(main())
