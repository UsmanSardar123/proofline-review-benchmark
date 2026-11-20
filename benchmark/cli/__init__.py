"""Command-line interface and execution automation for the Proofline AI Review Benchmark."""

from benchmark.cli.commands import (
    cmd_calibrate,
    cmd_init_db,
    cmd_list_batches,
    cmd_list_cases,
    cmd_list_providers,
    cmd_report,
    cmd_resume,
    cmd_run,
    cmd_show_attempt,
)
from benchmark.cli.main import build_parser, main

__all__ = [
    "build_parser",
    "main",
    "cmd_init_db",
    "cmd_list_cases",
    "cmd_list_providers",
    "cmd_list_batches",
    "cmd_run",
    "cmd_resume",
    "cmd_report",
    "cmd_show_attempt",
    "cmd_calibrate",
]
