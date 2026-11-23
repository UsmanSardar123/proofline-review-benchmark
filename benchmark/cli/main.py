"""Main entry point and argument parsing for the Proofline benchmark CLI."""

import argparse
import sys
from typing import Optional

from benchmark.cli.commands import (
    cmd_automate,
    cmd_calibrate,
    cmd_campaign,
    cmd_cloudflare_status,
    cmd_collect,
    cmd_ingest,
    cmd_init_db,
    cmd_list_batches,
    cmd_list_cases,
    cmd_list_providers,
    cmd_prompt,
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
    p_run.add_argument(
        "--manual",
        action="store_true",
        help="Schedule batch for manual / web-imported review ingestion without immediate dispatch",
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

    # 10. prompt
    p_prompt = subparsers.add_parser(
        "prompt",
        help="Generate and display or export standardized review prompt for a case",
    )
    p_prompt.add_argument(
        "--case",
        required=True,
        help="Benchmark case number (1-8) or case ID (e.g. 1 or case-01)",
    )
    p_prompt.add_argument(
        "--context",
        choices=["code-only", "code-and-snapshot"],
        default="code-only",
        help="Context condition to format (default: code-only)",
    )
    p_prompt.add_argument(
        "--output",
        default=None,
        help="Optional file path to write generated prompt to (defaults to stdout)",
    )
    p_prompt.add_argument(
        "--instructions",
        default=None,
        help="Optional custom review instructions override",
    )

    # 11. ingest
    p_ingest = subparsers.add_parser(
        "ingest",
        help="Import external or manual AI review response from Markdown file into an attempt",
    )
    p_ingest.add_argument(
        "--batch-id",
        required=True,
        help="Identifier of the batch containing the target attempt",
    )
    p_ingest.add_argument(
        "--provider",
        required=True,
        help="Provider identifier (e.g. chatgpt-web, claude-web, proofline, coderabbit)",
    )
    p_ingest.add_argument(
        "--case",
        required=True,
        help="Benchmark case number (1-8) or case ID (e.g. 1 or case-01)",
    )
    p_ingest.add_argument(
        "--file",
        dest="file_path",
        required=True,
        help="Path to Markdown file containing the raw AI review response",
    )
    p_ingest.add_argument(
        "--context",
        choices=["code-only", "code-and-snapshot"],
        default=None,
        help="Context condition to target (optional if batch contains only one condition for this case)",
    )
    p_ingest.add_argument(
        "--model",
        default=None,
        help="Optional model name override (e.g. gpt-4o, claude-3-5-sonnet)",
    )
    p_ingest.add_argument(
        "--tokens",
        default=None,
        help="Optional token counts formatted as 'prompt,completion' integers",
    )
    p_ingest.add_argument(
        "--duration-ms",
        type=int,
        default=None,
        help="Optional review duration in milliseconds",
    )
    p_ingest.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite if target attempt is already marked COMPLETED",
    )

    # 12. automate
    p_auto = subparsers.add_parser(
        "automate",
        help="Phase 2 automation pipeline: synchronize prompts, discover review files, ingest, score, and regenerate reports",
    )
    p_auto.add_argument(
        "--no-ingest",
        action="store_true",
        help="Skip automatic ingestion of discovered review files",
    )
    p_auto.add_argument(
        "--no-prompts",
        action="store_true",
        help="Skip prompt regeneration and synchronization",
    )
    p_auto.add_argument(
        "--no-reports",
        action="store_true",
        help="Skip batch reports export",
    )
    p_auto.add_argument(
        "--prompts-dir",
        default=None,
        help="Directory to store individualized review prompt files",
    )
    p_auto.add_argument(
        "--reviews-dir",
        default=None,
        help="Directory to monitor and scan for newly saved reviewer responses",
    )
    p_auto.add_argument(
        "--reports-dir",
        default=None,
        help="Directory to output regenerated comparative reports",
    )

    # 13. collect
    p_collect = subparsers.add_parser(
        "collect",
        help="Automated review collection: pre-flight planning, token estimation, dry-run simulation, and authorized API dispatch",
    )
    p_collect.add_argument(
        "--plan",
        action="store_true",
        help="Display scheduled collection matrix with token and cost breakdown",
    )
    p_collect.add_argument(
        "--estimate-cost",
        action="store_true",
        help="Calculate projected API cost breakdown in USD",
    )
    p_collect.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate collection workflow without making external API calls",
    )
    p_collect.add_argument(
        "--run",
        action="store_true",
        help="Dispatch live collection (requires --allow-paid-api and API keys)",
    )
    p_collect.add_argument(
        "--allow-paid-api",
        action="store_true",
        help="Safety gate: explicitly authorize billable external API requests",
    )
    p_collect.add_argument(
        "--cost-limit",
        type=float,
        default=2.0,
        help="Maximum financial ceiling in USD (default: $2.00)",
    )
    p_collect.add_argument(
        "--provider",
        default=None,
        help="Optional provider filter (e.g. chatgpt-web, claude-web)",
    )

    # 14. cloudflare-status
    p_cf = subparsers.add_parser(
        "cloudflare-status",
        help="Inspect Cloudflare Workers AI configuration, selected model, and daily local Neuron quota without making inference requests",
    )
    p_cf.add_argument(
        "--model",
        default=None,
        help="Optional model ID to inspect (defaults to configured default model)",
    )

    # 15. campaign
    p_camp = subparsers.add_parser(
        "campaign",
        help="Safe automated campaign runner for Cases 03-08 under Cloudflare Workers AI",
    )
    p_camp.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Execute simulated campaign workflow without external API calls",
    )
    p_camp.add_argument(
        "--run",
        action="store_true",
        help="Execute live campaign reviews sequentially (requires explicit authorization)",
    )
    p_camp.add_argument(
        "--cases",
        default="3-8",
        help="Cases to evaluate in campaign: '3-8' (default), or comma-separated numbers",
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
                manual=args.manual,
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
        elif args.command == "prompt":
            return cmd_prompt(
                case=args.case,
                context=args.context,
                output=args.output,
                instructions=args.instructions,
            )
        elif args.command == "ingest":
            return cmd_ingest(
                batch_id=args.batch_id,
                provider=args.provider,
                case=args.case,
                file_path=args.file_path,
                context=args.context,
                model=args.model,
                tokens=args.tokens,
                duration_ms=args.duration_ms,
                force=args.force,
                db_path=args.db_path,
            )
        elif args.command == "automate":
            return cmd_automate(
                auto_ingest=not args.no_ingest,
                regenerate_prompts=not args.no_prompts,
                regenerate_reports=not args.no_reports,
                prompts_dir=args.prompts_dir,
                reviews_dir=args.reviews_dir,
                reports_dir=args.reports_dir,
                db_path=args.db_path,
            )
        elif args.command == "collect":
            return cmd_collect(
                show_plan=args.plan,
                estimate_cost=args.estimate_cost,
                dry_run=args.dry_run,
                run=args.run,
                allow_paid_api=args.allow_paid_api,
                cost_limit=args.cost_limit,
                provider=args.provider,
                db_path=args.db_path,
            )
        elif args.command == "cloudflare-status":
            return cmd_cloudflare_status(model=args.model)
        elif args.command == "campaign":
            return cmd_campaign(
                dry_run=not args.run or args.dry_run,
                run=args.run,
                cases=args.cases,
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
