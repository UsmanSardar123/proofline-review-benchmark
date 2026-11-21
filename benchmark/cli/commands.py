"""Command implementations for benchmark CLI operations."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Optional

from benchmark.cases.context import ContextManager
from benchmark.cases.registry import CaseRegistry
from benchmark.config import get_db_path
from benchmark.db.connection import get_connection
from benchmark.db.migrations import get_current_version, migrate_benchmark_db
from benchmark.db.repositories import (
    AttemptRepository,
    AttemptScoreRepository,
    BatchRepository,
    CaseRepository,
    EvaluationRepository,
    FindingRepository,
    GroundTruthRepository,
    ResponseRepository,
    RunEventRepository,
)
from benchmark.domain.enums import AttemptStatus, ContextCondition
from benchmark.orchestrator.engine import BenchmarkOrchestrator
from benchmark.providers.registry import ProviderRegistry
from benchmark.scoring.calibration import CalibrationRegistry
from benchmark.scoring.heldout import PartitionManager


def cmd_init_db(db_path: Optional[str] = None) -> int:
    """Initialize benchmark database schema and apply pending migrations."""
    target_path = Path(db_path) if db_path else get_db_path()
    conn = get_connection(target_path)
    try:
        applied = migrate_benchmark_db(conn)
        ver = get_current_version(conn)
        print(f"[OK] Benchmark database initialized at: {target_path}")
        if applied:
            print(f"[OK] Applied migrations: {applied} (Current schema version: {ver})")
        else:
            print(f"[OK] Schema is up to date (Current schema version: {ver})")
        return 0
    finally:
        conn.close()


def cmd_list_cases(partition: str = "all", db_path: Optional[str] = None) -> int:
    """List benchmark cases with partition assignments and deployment snapshots."""
    registry = CaseRegistry()
    cases = registry.load_all_cases()

    filter_partition = partition.lower() if partition else "all"
    if filter_partition == "calibration":
        cases = [c for c in cases if c.id in PartitionManager.CALIBRATION_CASES]
    elif filter_partition == "heldout":
        cases = [c for c in cases if c.id in PartitionManager.HELDOUT_CASES]
    elif filter_partition != "all":
        print(f"[ERROR] Invalid partition '{partition}'. Must be 'all', 'calibration', or 'heldout'.", file=sys.stderr)
        return 1

    print("\n" + "=" * 95)
    print(f"{'Case ID':<10} {'#':<3} {'Partition':<13} {'Snapshot':<10} {'Base -> Head':<18} {'Title'}")
    print("-" * 95)
    for c in cases:
        part_name = "Calibration" if c.id in PartitionManager.CALIBRATION_CASES else "Held-Out"
        snap_str = "Yes" if c.has_deployment_snapshot else "No"
        commits = f"{c.baseline_commit}..{c.target_commit}"
        print(f"{c.id:<10} {c.case_number:<3} {part_name:<13} {snap_str:<10} {commits:<18} {c.title}")
    print("=" * 95)
    print(f"Total cases listed: {len(cases)} (Filter: {filter_partition})\n")
    return 0


def cmd_list_providers() -> int:
    """List registered AI reviewer provider adapters and credential statuses."""
    registry = ProviderRegistry()
    registered = registry.list_registered()

    auth_env_keys = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "coderabbit": "CODERABBIT_API_KEY",
        "greptile": "GREPTILE_API_KEY",
        "mock": None,
        "mock-reviewer": None,
        "chatgpt-web": None,
        "claude-web": None,
        "proofline": None,
        "greptile-web": None,
        "manual": None,
    }

    manual_providers = {"chatgpt-web", "claude-web", "proofline", "greptile-web", "manual"}

    print("\n" + "=" * 80)
    print(f"{'Provider ID':<16} {'Display Name':<28} {'Default Model':<20} {'Status'}")
    print("-" * 80)
    for p_id in registered:
        try:
            adapter = registry.get_adapter(p_id, dry_run=True)
            display = adapter.display_name
            model = adapter.default_model
        except Exception as exc:
            display = "Unknown"
            model = "unknown"

        env_key = auth_env_keys.get(p_id)
        if p_id in manual_providers:
            status = "Ready (Zero-Cost Manual/Web Import)"
        elif env_key is None:
            status = "Ready (Mock/Local)"
        elif os.environ.get(env_key):
            status = f"Ready (Live API Key: {env_key[:4]}...)"
        else:
            status = f"Dry-Run Only (Missing {env_key})"

        print(f"{p_id:<16} {display:<28} {model:<20} {status}")
    print("=" * 80 + "\n")
    return 0


def cmd_list_batches(limit: int = 20, db_path: Optional[str] = None) -> int:
    """List historical benchmark batches and execution statuses."""
    conn = get_connection(db_path)
    try:
        migrate_benchmark_db(conn)
        batch_repo = BatchRepository(conn)
        batches = batch_repo.list_all(limit=limit)

        if not batches:
            print("\n[INFO] No benchmark batches recorded yet. Run 'benchmark run' to schedule one.\n")
            return 0

        print("\n" + "=" * 90)
        print(f"{'Batch ID':<16} {'Status':<15} {'Planned':<9} {'Created / Started':<26} {'Batch Name'}")
        print("-" * 90)
        for b in batches:
            started = b.started_at or "Not started"
            print(f"{b.id:<16} {b.status:<15} {b.planned_attempts_count:<9} {started:<26} {b.batch_name}")
        print("=" * 90)
        print(f"Showing up to {limit} recent batches.\n")
        return 0
    finally:
        conn.close()


def cmd_run(
    experiment_id: Optional[str] = None,
    batch_name: Optional[str] = None,
    providers: str = "mock",
    cases: str = "all",
    context: str = "both",
    repeats: int = 1,
    dry_run: bool = False,
    calibration_profile: str = "standard-v1",
    output_dir: Optional[str] = None,
    title: Optional[str] = None,
    manual: bool = False,
    db_path: Optional[str] = None,
) -> int:
    """Schedule and execute a benchmark batch across specified cases and providers."""
    # 1. Parse and validate case selection
    case_arg = cases.strip().lower()
    if case_arg == "all":
        case_numbers = list(range(1, 9))
    elif case_arg == "calibration":
        case_numbers = PartitionManager.get_calibration_case_numbers()
    elif case_arg == "heldout":
        case_numbers = PartitionManager.get_heldout_case_numbers()
    else:
        try:
            case_numbers = [int(p.strip()) for p in cases.split(",") if p.strip()]
            for n in case_numbers:
                if not (1 <= n <= 8):
                    raise ValueError(f"Case number out of range (1..8): {n}")
        except ValueError as exc:
            print(f"[ERROR] Invalid cases argument '{cases}': {exc}", file=sys.stderr)
            return 1

    # 2. Parse and validate provider selection
    prov_arg = providers.strip().lower()
    registry = ProviderRegistry()
    available = registry.list_registered()
    if prov_arg == "all":
        provider_ids = ["mock", "anthropic", "openai", "coderabbit"]
    else:
        provider_ids = [p.strip().lower() for p in providers.split(",") if p.strip()]
        for p_id in provider_ids:
            if p_id not in available:
                print(
                    f"[ERROR] Unknown provider '{p_id}'. Available providers: {available}",
                    file=sys.stderr,
                )
                return 1

    # 3. Parse and validate context condition
    ctx_arg = context.strip().lower()
    if ctx_arg == "both":
        contexts = [ContextCondition.CODE_ONLY, ContextCondition.CODE_AND_SNAPSHOT]
    elif ctx_arg in ("code-only", "code_only"):
        contexts = [ContextCondition.CODE_ONLY]
    elif ctx_arg in ("code-and-snapshot", "code_and_snapshot", "snapshot"):
        contexts = [ContextCondition.CODE_AND_SNAPSHOT]
    else:
        print(f"[ERROR] Invalid context '{context}'. Must be 'code-only', 'code-and-snapshot', or 'both'.", file=sys.stderr)
        return 1

    # 4. Parse calibration profile
    try:
        profile = CalibrationRegistry.get(calibration_profile)
    except KeyError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    # 5. Anti-leak isolation verification
    if case_arg == "calibration":
        evaluated_case_ids = [f"case-{n:02d}" for n in case_numbers]
        try:
            PartitionManager.verify_no_leakage(evaluated_case_ids)
        except ValueError as exc:
            print(f"[SECURITY VIOLATION] {exc}", file=sys.stderr)
            return 1

    # 6. Database connection & Orchestrator instantiation
    conn = get_connection(db_path)
    try:
        migrate_benchmark_db(conn)
        exp_id = experiment_id or f"exp-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
        b_name = batch_name or f"Benchmark Batch ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')})"

        orchestrator = BenchmarkOrchestrator(conn, calibration_profile=profile)

        print("\n" + "=" * 70)
        print("PROOF-LINE AI REVIEW BENCHMARK EXECUTION")
        print("=" * 70)
        print(f"Experiment ID:       {exp_id}")
        print(f"Batch Name:          {b_name}")
        print(f"Providers ({len(provider_ids)}):        {', '.join(provider_ids)}")
        print(f"Cases ({len(case_numbers)}):            {case_numbers}")
        print(f"Context Conditions:  {[c.value for c in contexts]}")
        print(f"Repeats:             {repeats}")
        print(f"Calibration Profile: {profile.name} (hash: {profile.profile_hash[:12]})")
        print(f"Execution Mode:      {'Dry-Run (Offline / Fixture)' if dry_run else 'Live API'}")
        print("=" * 70)

        # Schedule batch
        batch = orchestrator.schedule_batch(
            experiment_id=exp_id,
            batch_name=b_name,
            provider_ids=provider_ids,
            case_numbers=case_numbers,
            context_conditions=contexts,
            repeat_count=repeats,
        )
        print(f"\n[OK] Scheduled Batch ID: {batch.id} ({batch.planned_attempts_count} planned attempts)")

        if manual:
            conn.commit()
            print("\n" + "=" * 70)
            print("MANUAL EVALUATION BATCH SCHEDULED")
            print("=" * 70)
            print(f"Batch ID:          {batch.id}")
            print(f"Planned Attempts:  {batch.planned_attempts_count}")
            print(f"Status:            pending")
            print("-" * 70)
            print("Next steps to conduct zero-cost manual reviews:")
            print(f"1. Generate prompt:  python -m benchmark prompt --case <N> --context <context>")
            print(f"2. Feed to model:    Paste into ChatGPT, Claude.ai, or Proofline PR on GitHub")
            print(f"3. Ingest response:  python -m benchmark ingest --batch-id {batch.id} --provider <provider> --case <N> --file <review.md>")
            print("=" * 70 + "\n")
            return 0

        # Run batch
        print("[RUNNING] Executing review attempts...")
        summary = orchestrator.run_batch(batch.id, dry_run=dry_run)

        # Export reports if requested
        exported_files = None
        if output_dir:
            out_p = Path(output_dir)
            exported_files = orchestrator.export_report(batch.id, out_p, title=title)
            print(f"\n[OK] Exported benchmark reports to: {out_p.resolve()}")
            for k, f in exported_files.items():
                print(f"     - {k}: {f.name}")

        # Summary output
        print("\n" + "=" * 70)
        print("BATCH EXECUTION COMPLETE")
        print("=" * 70)
        print(f"Batch ID:          {summary['batch_id']}")
        print(f"Planned Attempts:  {summary['planned']}")
        print(f"Completed:         {summary['completed']}")
        print(f"Quota Exhausted:   {summary['quota_exhausted']}")
        print(f"Failed:            {summary['failed']}")
        print(f"Pending:           {summary['pending']}")
        print("=" * 70 + "\n")

        return 0
    except Exception as exc:
        print(f"[FATAL] Benchmark run failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def cmd_resume(
    batch_id: str,
    resume_quota: bool = False,
    dry_run: bool = False,
    output_dir: Optional[str] = None,
    title: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    """Recover and resume an interrupted or quota-halted benchmark batch."""
    conn = get_connection(db_path)
    try:
        migrate_benchmark_db(conn)
        batch_repo = BatchRepository(conn)
        batch = batch_repo.get_by_id(batch_id)
        if not batch:
            by_exp = batch_repo.list_for_experiment(batch_id)
            if by_exp:
                batch = by_exp[0]
                batch_id = batch.id
            else:
                print(f"[ERROR] Batch ID '{batch_id}' not found.", file=sys.stderr)
                return 1

        orchestrator = BenchmarkOrchestrator(conn)

        print("\n" + "=" * 70)
        print(f"RESUMING BENCHMARK BATCH: {batch_id}")
        print("=" * 70)
        print(f"Batch Name:        {batch.batch_name}")
        print(f"Current Status:    {batch.status}")
        print(f"Resume Quota:      {'Yes (re-attempting quota-halted)' if resume_quota else 'No'}")
        print(f"Dry-Run Mode:      {'Yes' if dry_run else 'No'}")
        print("=" * 70)

        summary = orchestrator.recover_and_resume_batch(
            batch_id,
            resume_quota=resume_quota,
            dry_run=dry_run,
        )

        if output_dir:
            out_p = Path(output_dir)
            exported = orchestrator.export_report(batch_id, out_p, title=title)
            print(f"\n[OK] Updated reports exported to: {out_p.resolve()}")

        print("\n" + "=" * 70)
        print("RESUME EXECUTION COMPLETE")
        print("=" * 70)
        print(f"Batch ID:          {summary['batch_id']}")
        print(f"Planned Attempts:  {summary['planned']}")
        print(f"Completed:         {summary['completed']}")
        print(f"Quota Exhausted:   {summary['quota_exhausted']}")
        print(f"Failed:            {summary['failed']}")
        print(f"Pending:           {summary['pending']}")
        print("=" * 70 + "\n")

        return 0
    except Exception as exc:
        print(f"[FATAL] Resume failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def cmd_report(
    batch_id: str,
    report_format: str = "markdown",
    output_dir: Optional[str] = None,
    title: Optional[str] = None,
    stdout: bool = False,
    db_path: Optional[str] = None,
) -> int:
    """Generate and display or export benchmark reports for a batch."""
    conn = get_connection(db_path)
    try:
        migrate_benchmark_db(conn)
        batch_repo = BatchRepository(conn)
        batch = batch_repo.get_by_id(batch_id)
        if not batch:
            by_exp = batch_repo.list_for_experiment(batch_id)
            if by_exp:
                batch = by_exp[0]
                batch_id = batch.id
            else:
                print(f"[ERROR] Batch ID '{batch_id}' not found.", file=sys.stderr)
                return 1

        orchestrator = BenchmarkOrchestrator(conn)
        report = orchestrator.generate_report(batch_id, title=title)

        if output_dir:
            out_p = Path(output_dir)
            files = orchestrator.export_report(batch_id, out_p, title=title)
            print(f"[OK] Exported full benchmark reports to: {out_p.resolve()}")
            for name, path in files.items():
                print(f"     - {name}: {path.name}")

        fmt = report_format.lower()
        if stdout or not output_dir:
            if fmt == "markdown":
                print("\n" + report["markdown"] + "\n")
            elif fmt == "json":
                print(report["json"])
            elif fmt == "csv":
                print("\n# MATRIX CSV\n" + report["csv"]["matrix"])
                print("\n# ABLATION CSV\n" + report["csv"]["ablation"])
                print("\n# DENOMINATORS CSV\n" + report["csv"]["denominators"])
                print("\n# PARTITION CSV\n" + report["csv"]["partition"])
            elif fmt == "all":
                print("\n" + report["markdown"] + "\n")
            else:
                print(f"[ERROR] Unknown format '{report_format}'. Must be 'markdown', 'json', 'csv', or 'all'.", file=sys.stderr)
                return 1

        return 0
    except Exception as exc:
        print(f"[FATAL] Report generation failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def cmd_show_attempt(
    attempt_id: str,
    full_response: bool = False,
    db_path: Optional[str] = None,
) -> int:
    """Inspect and trace a single review attempt back to original review and scores."""
    conn = get_connection(db_path)
    try:
        migrate_benchmark_db(conn)
        att_repo = AttemptRepository(conn)
        resp_repo = ResponseRepository(conn)
        find_repo = FindingRepository(conn)
        eval_repo = EvaluationRepository(conn)
        score_repo = AttemptScoreRepository(conn)
        event_repo = RunEventRepository(conn)
        case_repo = CaseRepository(conn)
        gt_repo = GroundTruthRepository(conn)

        attempt = att_repo.get_by_id(attempt_id)
        if not attempt:
            print(f"[ERROR] Attempt ID '{attempt_id}' not found.", file=sys.stderr)
            return 1

        case = case_repo.get_by_id(attempt.case_id)
        response = resp_repo.get_by_attempt_id(attempt_id)
        findings = find_repo.list_for_attempt(attempt_id)
        evaluations = eval_repo.list_for_attempt(attempt_id)
        score = score_repo.get_by_attempt_id(attempt_id)
        events = event_repo.list_for_attempt(attempt_id)
        ground_truths = gt_repo.list_for_case(attempt.case_id)

        print("\n" + "=" * 80)
        print(f"REVIEW ATTEMPT AUDIT & TRACEABILITY REPORT: {attempt_id}")
        print("=" * 80)
        print(f"Batch ID:          {attempt.batch_id}")
        print(f"Provider:          {attempt.provider_id}")
        print(f"Case:              {attempt.case_id} ({case.title if case else 'Unknown'})")
        print(f"Context Condition: {attempt.context_condition.value}")
        print(f"Model Name:        {attempt.model_name}")
        print(f"Attempt Type:      {attempt.attempt_type.value} (#{attempt.attempt_number})")
        print(f"Commit Range:      {attempt.base_commit} -> {attempt.head_commit}")
        print(f"Status:            {attempt.status.value}")
        print(f"Duration:          {attempt.duration_ms} ms (retries: {attempt.retry_count})")
        if attempt.error_reason:
            print(f"Error Reason:      {attempt.error_reason}")

        # Review Response
        print("\n" + "-" * 80)
        print("1. CAPTURED REVIEW RESPONSE")
        print("-" * 80)
        if response:
            prompt_tok = response.prompt_tokens or 0
            comp_tok = response.completion_tokens or 0
            print(f"HTTP Status:       {response.http_status}")
            print(f"Tokens:            Prompt={prompt_tok}, Completion={comp_tok}, Total={prompt_tok + comp_tok}")
            print("\nResponse Body:")
            body = response.raw_content
            if not full_response and len(body) > 800:
                print(body[:800] + f"\n... [truncated {len(body) - 800} chars; use --full to view entire response]")
            else:
                print(body)
        else:
            print("[None - No response captured]")

        # Findings & Evaluations
        print("\n" + "-" * 80)
        print(f"2. EXTRACTED FINDINGS & EVALUATIONS ({len(findings)} findings)")
        print("-" * 80)
        if findings:
            eval_by_find = {e.finding_id: e for e in evaluations}
            for idx, f in enumerate(findings, 1):
                ev = eval_by_find.get(f.id)
                classification = ev.classification.value if ev else "UNEVALUATED"
                ev_cite = " [Cited Deployment Evidence]" if ev and ev.cites_deployment_evidence else ""
                print(f"Finding #{idx} [{f.id}]:")
                print(f"  Target:          {f.file_path}:{f.line_start or '?'}-{f.line_end or '?'}")
                print(f"  Severity:        {f.reported_severity or 'None'}")
                print(f"  Classification:  {classification}{ev_cite}")
                if ev and ev.rationale:
                    print(f"  Rationale:       {ev.rationale}")
                print(f"  Summary:         {f.summary}")
                if f.raw_comment_slice:
                    print(f"  Raw Comment:     {f.raw_comment_slice.strip()[:150]}...")
                print()
        else:
            print("Zero findings extracted (Reviewer raised no objections).")

        # Ground Truth Comparison & Score
        print("-" * 80)
        print("3. GROUND TRUTH DEFECT COMPARISON & SCORING")
        print("-" * 80)
        if ground_truths:
            for gt in ground_truths:
                print(f"Ground Truth Defect: [{gt.id}] {gt.defect_category.value}")
                print(f"  Target File/Line:  {gt.target_file}:{gt.target_lines}")
                print(f"  Expected Action:   {gt.expected_action}")
                print(f"  Description:       {gt.description}")
        else:
            print("No ground truth defect registered (Benign change expected to APPROVE).")

        if score:
            print(f"\nFinal Scored Metrics:")
            print(f"  True Positives (TP):     {score.tp_count}")
            print(f"  False Positives (FP):    {score.fp_count}")
            print(f"  False Negatives (FN):    {score.fn_count}")
            print(f"  Valid Unexpected (VUF):  {score.vuf_count}")
            print(f"  Precision:               {score.precision_rate:.4f}")
            print(f"  Recall:                  {score.recall_rate:.4f}")
            print(f"  F1 Score:                {score.f1_metric:.4f}")
            print(f"  Clean Pass:              {'YES' if score.passed_cleanly else 'NO'}")
            print(f"  Computed At:             {score.computed_at}")
        else:
            print("\n[Score: None calculated]")

        # Audit Log Events
        print("\n" + "-" * 80)
        print(f"4. LIFECYCLE AUDIT LOG ({len(events)} events)")
        print("-" * 80)
        for ev in events:
            trans = f" ({ev.from_state} -> {ev.to_state})" if ev.from_state or ev.to_state else ""
            print(f"  [{ev.created_at}] {ev.event_type:<20}{trans} : {ev.message}")
        print("=" * 80 + "\n")

        return 0
    except Exception as exc:
        print(f"[FATAL] Failed to inspect attempt: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def cmd_calibrate(
    batch_id: Optional[str] = None,
    profile_name: str = "all",
    db_path: Optional[str] = None,
) -> int:
    """Inspect calibration profiles and evaluate partition generalization."""
    profiles = CalibrationRegistry.get_all_profiles()

    print("\n" + "=" * 90)
    print("CALIBRATION PROFILES & PARAMETER FINGERPRINTS")
    print("=" * 90)
    print(f"{'Profile Name':<16} {'Tolerance':<12} {'Threshold':<12} {'Min KWs':<10} {'SHA-256 Hash'}")
    print("-" * 90)
    for p in profiles:
        print(f"{p.name:<16} {p.line_tolerance:<12} {p.match_threshold:<12} {p.min_keyword_matches:<10} {p.profile_hash[:16]}")
    print("=" * 90)

    if batch_id:
        conn = get_connection(db_path)
        try:
            migrate_benchmark_db(conn)
            score_repo = AttemptScoreRepository(conn)
            att_repo = AttemptRepository(conn)

            attempts = att_repo.list_for_batch(batch_id)
            if not attempts:
                print(f"\n[ERROR] No attempts found for batch '{batch_id}'.", file=sys.stderr)
                return 1

            cal_scores = []
            held_scores = []
            for att in attempts:
                sc = score_repo.get_by_attempt_id(att.id)
                if not sc:
                    continue
                if att.case_id in PartitionManager.CALIBRATION_CASES:
                    cal_scores.append(sc)
                elif att.case_id in PartitionManager.HELDOUT_CASES:
                    held_scores.append(sc)

            if not cal_scores and not held_scores:
                print(f"\n[WARNING] Batch '{batch_id}' contains no scored attempts.", file=sys.stderr)
                return 0

            gen_report = PartitionManager.evaluate_generalization(cal_scores, held_scores)
            print("\n" + "=" * 80)
            print(f"OUT-OF-SAMPLE GENERALIZATION ANALYSIS (Batch: {batch_id})")
            print("=" * 80)
            print(f"Calibration Attempts ({gen_report.calibration_count}):")
            print(f"  Precision: {gen_report.calibration_precision:.4f} | Recall: {gen_report.calibration_recall:.4f} | F1: {gen_report.calibration_f1:.4f}")
            print(f"Held-Out Attempts ({gen_report.heldout_count}):")
            print(f"  Precision: {gen_report.heldout_precision:.4f} | Recall: {gen_report.heldout_recall:.4f} | F1: {gen_report.heldout_f1:.4f}")
            print(f"Generalization Delta (Held-Out F1 - Calibration F1): {gen_report.generalization_delta:+.4f}")
            print(f"Overfitting Detected: {'YES (Delta < -0.25)' if gen_report.is_overfitted else 'NO (Robust Generalization)'}")
            print("=" * 80 + "\n")
        finally:
            conn.close()

    return 0


def cmd_prompt(
    case: int | str,
    context: str = "code-only",
    output: Optional[str] = None,
    instructions: Optional[str] = None,
) -> int:
    """Generate and display or export the standardized review prompt for a case."""
    try:
        case_num = int(str(case).lower().replace("case-", ""))
        if not (1 <= case_num <= 8):
            raise ValueError(f"Case number out of range (1..8): {case_num}")
    except ValueError as exc:
        print(f"[ERROR] Invalid case '{case}': {exc}", file=sys.stderr)
        return 1

    ctx_arg = context.strip().lower()
    if ctx_arg in ("code-and-snapshot", "code_and_snapshot", "snapshot"):
        cond = ContextCondition.CODE_AND_SNAPSHOT
    elif ctx_arg in ("code-only", "code_only"):
        cond = ContextCondition.CODE_ONLY
    else:
        print(f"[ERROR] Invalid context '{context}'. Must be 'code-only' or 'code-and-snapshot'.", file=sys.stderr)
        return 1

    try:
        ctx_mgr = ContextManager()
        review_context = ctx_mgr.build_context(case_num, cond)
        prompt_text = ContextManager.format_review_prompt(review_context, custom_instructions=instructions)

        if output:
            out_file = Path(output)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(prompt_text, encoding="utf-8")
            print(f"[OK] Generated review prompt for Case {case_num:02d} ({cond.value}) -> {out_file.resolve()}")
            print(f"     Prompt size: {len(prompt_text)} characters, Context Hash: {review_context.context_hash[:16]}")
        else:
            print(prompt_text)

        return 0
    except Exception as exc:
        print(f"[FATAL] Failed to generate review prompt: {exc}", file=sys.stderr)
        return 1


def cmd_ingest(
    batch_id: str,
    provider: str,
    case: int | str,
    file_path: str,
    context: Optional[str] = None,
    model: Optional[str] = None,
    tokens: Optional[str] = None,
    duration_ms: Optional[int] = None,
    force: bool = False,
    db_path: Optional[str] = None,
) -> int:
    """Ingest a manual review response from file into a scheduled benchmark attempt."""
    # 1. Validate file
    review_file = Path(file_path)
    if not review_file.is_file():
        print(f"[ERROR] Review file not found: {file_path}", file=sys.stderr)
        return 1

    try:
        raw_content = review_file.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"[ERROR] Failed to read review file '{file_path}': {exc}", file=sys.stderr)
        return 1

    if not raw_content or not raw_content.strip():
        print(f"[ERROR] Review file '{file_path}' is empty.", file=sys.stderr)
        return 1

    # 2. Parse case number
    try:
        case_num = int(str(case).lower().replace("case-", ""))
        target_case_id = f"case-{case_num:02d}"
    except ValueError as exc:
        print(f"[ERROR] Invalid case identifier '{case}': {exc}", file=sys.stderr)
        return 1

    # 3. Parse optional context condition
    target_condition = None
    if context:
        ctx_lower = context.strip().lower()
        if ctx_lower in ("code-and-snapshot", "code_and_snapshot", "snapshot"):
            target_condition = ContextCondition.CODE_AND_SNAPSHOT
        elif ctx_lower in ("code-only", "code_only"):
            target_condition = ContextCondition.CODE_ONLY
        else:
            print(f"[ERROR] Invalid context condition '{context}'. Must be 'code-only' or 'code-and-snapshot'.", file=sys.stderr)
            return 1

    # 4. Parse optional tokens (prompt,completion)
    prompt_tokens = None
    completion_tokens = None
    if tokens:
        try:
            tok_parts = [int(p.strip()) for p in tokens.split(",") if p.strip()]
            if len(tok_parts) >= 1:
                prompt_tokens = tok_parts[0]
            if len(tok_parts) >= 2:
                completion_tokens = tok_parts[1]
        except ValueError:
            print(f"[WARNING] Invalid --tokens format '{tokens}'. Expected 'prompt,completion' integers.", file=sys.stderr)

    # 5. Connect and find matching attempt
    conn = get_connection(db_path)
    try:
        migrate_benchmark_db(conn)
        batch_repo = BatchRepository(conn)
        att_repo = AttemptRepository(conn)

        batch = batch_repo.get_by_id(batch_id)
        if not batch:
            by_exp = batch_repo.list_for_experiment(batch_id)
            if by_exp:
                batch = by_exp[0]
                batch_id = batch.id
            else:
                print(f"[ERROR] Batch ID '{batch_id}' not found.", file=sys.stderr)
                return 1

        attempts = att_repo.list_for_batch(batch_id)
        matching = [
            a for a in attempts
            if a.provider_id.lower() == provider.lower() and a.case_id == target_case_id
        ]

        if target_condition:
            matching = [a for a in matching if a.context_condition == target_condition]

        if not matching:
            cond_str = f" with context '{target_condition.value}'" if target_condition else ""
            print(
                f"[ERROR] No attempt found for Batch '{batch_id}', Provider '{provider}', Case '{target_case_id}'{cond_str}.",
                file=sys.stderr,
            )
            return 1

        if len(matching) > 1:
            print(
                f"[ERROR] Multiple ({len(matching)}) matching attempts found for Case {target_case_id}. "
                f"Please specify --context {{code-only,code-and-snapshot}} to disambiguate.",
                file=sys.stderr,
            )
            return 1

        target_attempt = matching[0]

        # Check duplicate
        if target_attempt.status == AttemptStatus.COMPLETED and not force:
            print(
                f"[ERROR] Attempt '{target_attempt.id}' is already COMPLETED. "
                f"Use --force to overwrite and re-ingest.",
                file=sys.stderr,
            )
            return 1

        orchestrator = BenchmarkOrchestrator(conn)
        updated_att, score = orchestrator.ingest_review(
            attempt_id=target_attempt.id,
            raw_content=raw_content,
            model_name=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_ms=duration_ms,
            overwrite=force,
        )

        print("\n" + "=" * 80)
        print("MANUAL REVIEW INGESTION & SCORING SUCCESS")
        print("=" * 80)
        print(f"Batch ID:          {batch_id}")
        print(f"Attempt ID:        {updated_att.id}")
        print(f"Provider:          {updated_att.provider_id}")
        print(f"Model:             {updated_att.model_name}")
        print(f"Case:              {updated_att.case_id}")
        print(f"Context Condition: {updated_att.context_condition.value}")
        print(f"Status:            {updated_att.status.value}")
        print(f"Review Length:     {len(raw_content)} characters (from {review_file.name})")
        print("-" * 80)
        print("EVALUATION & SCORING RESULT:")
        print(f"  True Positives (TP):     {score.tp_count}")
        print(f"  False Positives (FP):    {score.fp_count}")
        print(f"  False Negatives (FN):    {score.fn_count}")
        print(f"  Valid Unexpected (VUF):  {score.vuf_count}")
        print(f"  Precision:               {score.precision_rate:.4f}")
        print(f"  Recall:                  {score.recall_rate:.4f}")
        print(f"  F1 Score:                {score.f1_metric:.4f}")
        print(f"  Clean Pass:              {'YES' if score.passed_cleanly else 'NO'}")
        print("=" * 80 + "\n")
        return 0
    except Exception as exc:
        print(f"[FATAL] Ingestion failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()
