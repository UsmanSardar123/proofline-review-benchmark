"""Formatters for benchmark matrices and reports: Markdown, CSV, and structured JSON."""

import csv
from io import StringIO
import json
from typing import Any, Optional

from benchmark.domain.enums import ContextCondition
from benchmark.reporting.matrix import (
    AblationMatrix,
    BenchmarkMatrixGenerator,
    DenominatorSummary,
    ProviderCaseMatrix,
)


class MarkdownFormatter:
    """Renders benchmark matrices and summaries as GitHub-flavored Markdown tables."""

    @staticmethod
    def format_matrix(matrix: ProviderCaseMatrix, title: Optional[str] = None) -> str:
        lines = []
        heading = title or f"Provider vs Case Benchmark Matrix (Batch: {matrix.batch_id})"
        lines.append(f"### {heading}\n")

        headers = ["Provider"] + matrix.cases + ["P", "R", "F1", "Passed"]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        for p_id in matrix.providers:
            summary = matrix.provider_summaries.get(p_id)
            row = [p_id]
            for c_id in matrix.cases:
                cell = matrix.matrix.get(p_id, {}).get(c_id)
                if not cell:
                    row.append("-")
                elif cell.status != "COMPLETED":
                    row.append(f"`{cell.status}`")
                else:
                    symbol = "✓" if cell.outcome in ("TRUE_POSITIVE", "CLEAN_PASS") else "✗"
                    f1_str = f"{cell.f1_score:.2f}" if cell.f1_score is not None else "-"
                    ev_mark = " 🔍" if cell.cites_evidence else ""
                    row.append(f"{symbol} {cell.outcome[:2]} ({f1_str}){ev_mark}")

            prec = f"{summary.precision:.2f}" if summary else "-"
            rec = f"{summary.recall:.2f}" if summary else "-"
            f1 = f"{summary.f1_score:.2f}" if summary else "-"
            passed = f"{summary.clean_passes}" if summary else "-"
            row.extend([prec, rec, f1, passed])
            lines.append("| " + " | ".join(row) + " |")

        lines.append("\n*Legend: `✓ TP` = True Positive, `✓ CL` = Clean Pass on benign PR, `✗ FP` = False Positive, `✗ FN` = Missed Defect, `🔍` = Cited Deployment Evidence.*")
        return "\n".join(lines)

    @staticmethod
    def format_ablation(ablation: AblationMatrix) -> str:
        lines = []
        lines.append(f"### Context & Deployment Snapshot Ablation Study (Batch: {ablation.batch_id})\n")
        lines.append("| Provider | Case | Code-Only F1 | Code+Snap F1 | F1 Delta | Evidence Grounded? |")
        lines.append("| --- | --- | --- | --- | --- | --- |")

        for r in ablation.rows:
            c_f1 = f"{r.code_only_f1:.2f}" if r.code_only_f1 is not None else "-"
            s_f1 = f"{r.snapshot_f1:.2f}" if r.snapshot_f1 is not None else "-"
            delta_sign = "+" if r.f1_delta > 0 else ""
            delta_str = f"{delta_sign}{r.f1_delta:.2f}"
            grounded = "Yes (Gained)" if r.evidence_gain else ("Yes" if r.snapshot_cites_evidence else "No")
            lines.append(f"| {r.provider_id} | {r.case_id} | {c_f1} | {s_f1} | {delta_str} | {grounded} |")

        return "\n".join(lines)

    @staticmethod
    def format_denominators(denom: DenominatorSummary) -> str:
        lines = []
        lines.append(f"### Evaluation Breadth & Denominator Breakdown (Batch: {denom.batch_id})\n")
        lines.append("| Provider | Planned | Completed | Quota Halted | Failed | Pending | Completion Rate |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")

        for p_id, p_d in denom.providers.items():
            lines.append(
                f"| {p_id} | {p_d.planned} | {p_d.completed} | {p_d.quota_halted} | {p_d.failed} | {p_d.pending} | {p_d.completion_rate_pct:.1f}% |"
            )

        lines.append(
            f"| **Total** | **{denom.planned_total}** | **{denom.completed_total}** | **{denom.quota_halted_total}** | **{denom.failed_total}** | **{denom.pending_total}** | **{denom.completion_rate_pct:.1f}%** |"
        )
        return "\n".join(lines)


class CSVFormatter:
    """Renders benchmark comparisons and summaries as CSV strings for spreadsheet export."""

    @staticmethod
    def format_matrix_csv(matrix: ProviderCaseMatrix) -> str:
        output = StringIO()
        writer = csv.writer(output)
        headers = ["provider"] + matrix.cases + ["precision", "recall", "f1_score", "completed", "planned"]
        writer.writerow(headers)

        for p_id in matrix.providers:
            summary = matrix.provider_summaries.get(p_id)
            row = [p_id]
            for c_id in matrix.cases:
                cell = matrix.matrix.get(p_id, {}).get(c_id)
                if not cell:
                    row.append("")
                elif cell.status != "COMPLETED":
                    row.append(cell.status)
                else:
                    f1 = cell.f1_score if cell.f1_score is not None else ""
                    row.append(f"{cell.outcome}:{f1}")
            row.append(summary.precision if summary else "")
            row.append(summary.recall if summary else "")
            row.append(summary.f1_score if summary else "")
            row.append(summary.completed if summary else "")
            row.append(summary.total_planned if summary else "")
            writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def format_ablation_csv(ablation: AblationMatrix) -> str:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "provider_id", "case_id", "code_only_status", "code_only_f1",
            "code_only_detected", "code_only_cites_evidence", "snapshot_status",
            "snapshot_f1", "snapshot_detected", "snapshot_cites_evidence", "f1_delta", "evidence_gain"
        ])
        for r in ablation.rows:
            writer.writerow([
                r.provider_id, r.case_id, r.code_only_status, r.code_only_f1,
                r.code_only_detected, r.code_only_cites_evidence, r.snapshot_status,
                r.snapshot_f1, r.snapshot_detected, r.snapshot_cites_evidence,
                r.f1_delta, r.evidence_gain
            ])
        return output.getvalue()

    @staticmethod
    def format_denominators_csv(denom: DenominatorSummary) -> str:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["provider_id", "planned", "completed", "quota_halted", "failed", "pending", "completion_rate_pct"])
        for p_id, p_d in denom.providers.items():
            writer.writerow([p_id, p_d.planned, p_d.completed, p_d.quota_halted, p_d.failed, p_d.pending, p_d.completion_rate_pct])
        writer.writerow(["TOTAL", denom.planned_total, denom.completed_total, denom.quota_halted_total, denom.failed_total, denom.pending_total, denom.completion_rate_pct])
        return output.getvalue()


class JSONFormatter:
    """Serializes structured benchmark results to JSON."""

    @staticmethod
    def format_json(data: Any, indent: int = 2) -> str:
        def default_serializer(obj):
            if hasattr(obj, "__dict__"):
                return obj.__dict__
            return str(obj)

        return json.dumps(data, default=default_serializer, indent=indent)


class BenchmarkReportGenerator:
    """Combines matrices, ablation comparisons, and denominators into structured reports."""

    def __init__(self, db):
        self.generator = BenchmarkMatrixGenerator(db)

    def generate_full_report(
        self,
        batch_id: str,
        title: str = "Proofline AI Review Benchmark Execution Report",
    ) -> dict[str, Any]:
        """Generate a complete benchmark report in Markdown, structured dict, and CSV."""
        matrix = self.generator.generate_provider_case_matrix(batch_id)
        ablation = self.generator.generate_ablation_matrix(batch_id)
        denominators = self.generator.generate_denominator_summary(batch_id)

        md_matrix = MarkdownFormatter.format_matrix(matrix)
        md_ablation = MarkdownFormatter.format_ablation(ablation)
        md_denominators = MarkdownFormatter.format_denominators(denominators)

        full_markdown = (
            f"# {title}\n\n"
            f"**Batch ID:** `{batch_id}`\n\n"
            f"## 1. Denominator & Run Breadth\n\n{md_denominators}\n\n"
            f"## 2. Provider vs Case Comparison Matrix\n\n{md_matrix}\n\n"
            f"## 3. Deployment Context Ablation\n\n{md_ablation}\n"
        )

        csv_matrix = CSVFormatter.format_matrix_csv(matrix)
        csv_ablation = CSVFormatter.format_ablation_csv(ablation)
        csv_denominators = CSVFormatter.format_denominators_csv(denominators)

        structured_data = {
            "batch_id": batch_id,
            "title": title,
            "denominators": denominators.__dict__,
            "matrix": {
                "providers": matrix.providers,
                "cases": matrix.cases,
                "provider_summaries": {k: v.__dict__ for k, v in matrix.provider_summaries.items()},
            },
            "ablation": [r.__dict__ for r in ablation.rows],
        }

        return {
            "batch_id": batch_id,
            "markdown": full_markdown,
            "json": JSONFormatter.format_json(structured_data),
            "csv": {
                "matrix": csv_matrix,
                "ablation": csv_ablation,
                "denominators": csv_denominators,
            },
            "data": structured_data,
        }
