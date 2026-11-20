"""Main entry point and argument parsing for the Proofline benchmark CLI."""

import argparse
import sys
from typing import Optional

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


def build_parser() -> argparse.ArgumentParser:
    """Construct and configure the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="benchmark",
        description="Proofline AI Pull Request Review Benchmarking Platform",
    )
    parser.add_argument(
        "--db",
        dest="db_path",
        default=None,
        help="Path to benchmark SQLite database (defaults to benchmark.sqlite)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. init-db
    subparsers.add_parser(
        "init-db",
        help="Initialize benchmark database and run schema migrations",
    )

    # 2. list-cases
    p_cases = subparsers.add_parser(
        "list-cases",
        help="List benchmark cases, defect categories, and partition allocations",
    )
    p_cases.add_argument(
        "--partition",
        choices=["all", "calibration", "heldout"],
        default="all",
        help="Filter cases by partition (default: all)",
    )

    # 3. list-providers
    subparsers.add_parser(
        "list-providers",
        help="List registered AI reviewer provider adapters and auth status",
    )

    # 4. list-batches
    p_batches = subparsers.add_parser(
        "list-batches",
        help="List recent benchmark execution batches and status",
    )
    p_batches.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of recent batches to list (default: 20)",
    )

    # 5. run
    p_run = subparsers.add_parser(
        "run",
        help="Schedule and execute a benchmark batch across cases and providers",
    )
    p_run.add_argument(
        "--experiment-id",
        dest="experiment_id",
        default=None,
        help="Parent experiment identifier (default: auto-generated)",
    )
    p_run.add_argument(
        "--batch-name",
        dest="batch_name",
        default=None,
        help="Descriptive name for the execution batch",
    )
    p_run.add_argument(
        "--providers",
        default="mock",
        help="Comma-separated provider IDs (e.g. 'mock', 'anthropic,openai') or 'all' (default: mock)",
    )
    p_run.add_argument(
        "--cases",
        default="all",
        help="Cases to evaluate: 'all' (1-8), 'calibration' (1,2,3,7), 'heldout' (4,5,6,8), or comma-separated numbers (default: all)",
    )
    p_run.add_argument(
        "--context",
        choices=["both", "code-only", "code-and-snapshot"],
        default="both",
        help="Context condition to evaluate (default: both)",
    )
    p_run.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="Intentional repeat count per provider-case pair (default: 1)",
    )
    p_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute using deterministic mock / dry-run fixtures (zero API cost)",
    )
    p_run.add_argument(
        "--calibration-profile",
        default="standard-v1",
        help="Calibration profile for matching & scoring: standard-v1, strict-v1, lenient-v1 (default: standard-v1)",
    )
    p_run.add_argument(
        "--output-dir",
        default=None,
        help="Directory to save generated Markdown, CSV, and JSON reports",
    )
    p_run.add_argument(
        "--title",
        default=None,
        help="Optional report title",
    )

    # 6. resume
    p_resume = subparsers.add_parser(
        "resume",
        help="Recover and resume an interrupted or quota-halted batch",
    )
    p_resume.add_argument(
        "--batch-id",
        required=True,
        help="Identifier of the batch to resume",
    )
    p_resume.add_argument(
        "--resume-quota",
        action="store_true",
        help="Retry attempts that halted due to provider quota exhaustion",
    )
    p_resume.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute using dry-run fixture mode",
    )
    p_resume.add_argument(
        "--output-dir",
        default=None,
        help="Directory to export updated reports upon completion",
    )
    p_resume.add_argument(
        "--title",
        default=None,
        help="Optional report title",
    )

    # 7. report
    p_report = subparsers.add_parser(
        "report",
        help="Generate and export or display structured benchmark reports",
    )
    p_report.add_argument(
        "--batch-id",
        required=True,
        help="Identifier of the batch to report on",
    )
    p_report.add_argument(
        "--format",
        choices=["markdown", "json", "csv", "all"],
        default="markdown",
        help="Report format to display/export (default: markdown)",
    )
    p_report.add_argument(
        "--output-dir",
        default=None,
        help="Directory to export report files",
    )
    p_report.add_argument(
        "--stdout",
        action="store_true",
        help="Print report directly to stdout",
    )
    p_report.add_argument(
        "--title",
        default=None,
        help="Optional report title",
    )

    # 8. show-attempt
    p_show = subparsers.add_parser(
        "show-attempt",
        help="Audit and trace a review attempt back to original review and scores",
    )
    p_show.add_argument(
        "--attempt-id",
        required=True,
        help="Identifier of the review attempt to inspect",
    )
    p_show.add_argument(
        "--full",
        action="store_true",
        help="Display complete raw review response without truncation",
    )

    # 9. calibrate
    p_cal = subparsers.add_parser(
        "calibrate",
        help="Inspect calibration profiles and evaluate partition generalization",
    )
    p_cal.add_argument(
        "--batch-id",
        default=None,
        help="Optional batch ID to analyze calibration vs held-out generalization delta",
    )
    p_cal.add_argument(
        "--profile",
        default="all",
        help="Calibration profile to inspect (default: all)",
    )

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Execute benchmark command-line interface."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "init-db":
            return cmd_init_db(db_path=args.db_path)
        elif args.command == "list-cases":
            return cmd_list_cases(partition=args.partition, db_path=args.db_path)
        elif args.command == "list-providers":
            return cmd_list_providers()
        elif args.command == "list-batches":
            return cmd_list_batches(limit=args.limit, db_path=args.db_path)
        elif args.command == "run":
            return cmd_run(
                experiment_id=args.experiment_id,
                batch_name=args.batch_name,
                providers=args.providers,
                cases=args.cases,
                context=args.context,
                repeats=args.repeats,
                dry_run=args.dry_run,
                calibration_profile=args.calibration_profile,
                output_dir=args.output_dir,
                title=args.title,
                db_path=args.db_path,
            )
        elif args.command == "resume":
            return cmd_resume(
                batch_id=args.batch_id,
                resume_quota=args.resume_quota,
                dry_run=args.dry_run,
                output_dir=args.output_dir,
                title=args.title,
                db_path=args.db_path,
            )
        elif args.command == "report":
            return cmd_report(
                batch_id=args.batch_id,
                report_format=args.format,
                output_dir=args.output_dir,
                title=args.title,
                stdout=args.stdout,
                db_path=args.db_path,
            )
        elif args.command == "show-attempt":
            return cmd_show_attempt(
                attempt_id=args.attempt_id,
                full_response=args.full,
                db_path=args.db_path,
            )
        elif args.command == "calibrate":
            return cmd_calibrate(
                batch_id=args.batch_id,
                profile_name=args.profile,
                db_path=args.db_path,
            )
        else:
            parser.print_help(sys.stderr)
            return 1
    except KeyboardInterrupt:
        print("\n[ABORTED] Operation interrupted by user.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
