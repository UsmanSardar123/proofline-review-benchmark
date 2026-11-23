"""Automated ingestion, prompt synchronization, and report regeneration for Phase 2."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import re
from typing import Optional

from benchmark.cases.context import ContextManager
from benchmark.cases.registry import CaseRegistry
from benchmark.db.connection import get_connection
from benchmark.db.migrations import migrate_benchmark_db
from benchmark.db.repositories import (
    AttemptRepository,
    AttemptScoreRepository,
    BatchRepository,
    CaseRepository,
    ProviderRepository,
    ResponseRepository,
)
from benchmark.domain.enums import AttemptStatus, ContextCondition
from benchmark.orchestrator.engine import BenchmarkOrchestrator

logger = logging.getLogger(__name__)


@dataclass
class IngestionCandidate:
    """A discovered review file candidate matched to an attempt."""
    file_path: Path
    attempt_id: str
    batch_id: str
    provider_id: str
    case_id: str
    context_condition: str
    match_source: str  # 'header_attempt_id', 'header_metadata', 'sidecar_meta', 'manifest'
    raw_content: str
    content_hash_sha256: str
    is_valid: bool = True
    rejection_reason: Optional[str] = None


@dataclass
class AutomationSummary:
    """Summary of operations performed by the automation orchestrator."""
    discovered_pending_attempts: int = 0
    prompts_generated: int = 0
    review_files_scanned: int = 0
    eligible_matches: int = 0
    ingested_count: int = 0
    duplicate_skipped: int = 0
    rejected_count: int = 0
    reports_regenerated: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    ingested_details: list[dict] = field(default_factory=list)


class AutomationPipeline:
    """Coordinates prompt packaging, review file discovery, reliable ingestion, and reporting."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        prompts_dir: Optional[Path | str] = None,
        reviews_dir: Optional[Path | str] = None,
        reports_dir: Optional[Path | str] = None,
    ):
        self.db_path = db_path
        self.prompts_dir = Path(prompts_dir) if prompts_dir else Path("collection/pending_prompts")
        self.reviews_dir = Path(reviews_dir) if reviews_dir else Path("reviews")
        self.reports_dir = Path(reports_dir) if reports_dir else Path("reports")
        self.context_manager = ContextManager()
        self.case_registry = CaseRegistry()

    def run_automation_cycle(
        self,
        auto_ingest: bool = True,
        regenerate_prompts: bool = True,
        regenerate_reports: bool = True,
    ) -> AutomationSummary:
        """Execute a full automation sweep across pending attempts and saved review files."""
        summary = AutomationSummary()

        conn = get_connection(self.db_path)
        try:
            migrate_benchmark_db(conn)
            att_repo = AttemptRepository(conn)
            batch_repo = BatchRepository(conn)
            orchestrator = BenchmarkOrchestrator(conn)

            # 1. Discover all pending attempts
            pending_attempts = [
                a for a in att_repo.list_all() if a.status == AttemptStatus.PENDING
            ]
            summary.discovered_pending_attempts = len(pending_attempts)

            # 2. Synchronize / generate prompts for every pending attempt
            if regenerate_prompts:
                summary.prompts_generated = self.generate_pending_prompts(pending_attempts)

            # 3. Discover and match review files in reviews_dir
            candidates = self.scan_and_match_reviews(pending_attempts, conn)
            summary.review_files_scanned = len(candidates)

            # 4. Ingest eligible candidates
            if auto_ingest:
                for candidate in candidates:
                    if not candidate.is_valid:
                        summary.rejected_count += 1
                        summary.errors.append(
                            f"Rejected {candidate.file_path.name}: {candidate.rejection_reason}"
                        )
                        continue

                    # Verify target attempt is still pending
                    target_att = att_repo.get_by_id(candidate.attempt_id)
                    if not target_att or target_att.status != AttemptStatus.PENDING:
                        summary.duplicate_skipped += 1
                        continue

                    summary.eligible_matches += 1

                    # Execute reliable ingestion through BenchmarkOrchestrator
                    try:
                        updated_att, score = orchestrator.ingest_review(
                            attempt_id=candidate.attempt_id,
                            raw_content=candidate.raw_content,
                            model_name=self._resolve_model_name(candidate.provider_id),
                            overwrite=False,
                        )
                        summary.ingested_count += 1
                        summary.ingested_details.append({
                            "attempt_id": candidate.attempt_id,
                            "batch_id": candidate.batch_id,
                            "provider_id": candidate.provider_id,
                            "case_id": candidate.case_id,
                            "file": candidate.file_path.name,
                            "tp": score.tp_count,
                            "fp": score.fp_count,
                            "fn": score.fn_count,
                            "f1": score.f1_metric,
                        })
                    except Exception as exc:
                        summary.errors.append(
                            f"Failed ingesting {candidate.file_path.name} -> {candidate.attempt_id}: {exc}"
                        )

            # 5. Regenerate batch reports for all active batches
            if regenerate_reports:
                batches = batch_repo.list_all()
                for b in batches:
                    try:
                        out_p = self.reports_dir / b.id
                        out_p.mkdir(parents=True, exist_ok=True)
                        orchestrator.export_report(b.id, out_p)
                        summary.reports_regenerated.append(b.id)
                    except Exception as exc:
                        summary.errors.append(f"Report export failed for {b.id}: {exc}")

            # 6. Re-generate prompts index with updated pending statuses
            refreshed_pending = [
                a for a in att_repo.list_all() if a.status == AttemptStatus.PENDING
            ]
            self.generate_pending_prompts(refreshed_pending)

        finally:
            conn.close()

        return summary

    def generate_pending_prompts(self, pending_attempts: list) -> int:
        """Generate individualized, leak-free prompt files and index for all pending attempts."""
        self.prompts_dir.mkdir(parents=True, exist_ok=True)

        index_lines = [
            "# Pending Manual Review Collection Index",
            "",
            f"**Total Pending Attempts:** {len(pending_attempts)}  ",
            f"**Last Synchronized:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}  ",
            "",
            "## Instructions for the Reviewer",
            "1. Open the prompt file linked below for the respective Case, Provider, and Context condition.",
            "2. Copy the entire section under the `---` horizontal rule (the `# Pull Request Review:...` text).",
            "3. **Where to paste:**",
            "   - For `chatgpt-web`: Paste into a fresh session on [chatgpt.com](https://chatgpt.com) (GPT-4o).",
            "   - For `claude-web`: Paste into a fresh session on [claude.ai](https://claude.ai) (Claude 3.5/3.7 Sonnet).",
            "4. Copy the complete, unmodified markdown response from the AI reviewer.",
            "5. Save the response into a local file in `reviews/` (e.g. `reviews/case-03_claude_response.md`).",
            "   Include metadata header block or name it using `<case>_<context>_<provider>_response.md`.",
            "6. Run `python -m benchmark automate` to automatically match, ingest, score, and regenerate reports.",
            "",
            "## Pending Collection Table",
            "",
            "| # | Case | Provider | Context | Batch ID | Attempt ID | Prompt File |",
            "| :---: | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        # Clean existing prompt files if count changed
        for existing in self.prompts_dir.glob("case-*.md"):
            existing.unlink(missing_ok=True)

        count = 0
        sorted_attempts = sorted(
            pending_attempts,
            key=lambda a: (a.case_id, a.context_condition.value, a.provider_id, a.batch_id),
        )

        for idx, att in enumerate(sorted_attempts, 1):
            case_num = int(att.case_id.replace("case-", ""))
            cond = att.context_condition
            ctx = self.context_manager.build_context(case_num, cond)
            prompt = self.context_manager.format_review_prompt(ctx)

            provider_slug = "chatgpt" if "chatgpt" in att.provider_id else "claude"
            cond_slug = "code_only" if cond == ContextCondition.CODE_ONLY else "code_and_snapshot"
            filename = f"{att.case_id}_{cond_slug}_{provider_slug}_{att.id[:8]}.md"
            filepath = self.prompts_dir / filename

            header = f"""<!--
  METADATA FOR AUTOMATED INGESTION:
  attempt_id: {att.id}
  batch_id: {att.batch_id}
  provider_id: {att.provider_id}
  case_id: {att.case_id}
  context_condition: {att.context_condition.value}
-->
# BENCHMARK REVIEW PROMPT
- **Case ID:** {att.case_id}
- **Attempt ID:** {att.id}
- **Batch ID:** {att.batch_id}
- **Provider Target:** {att.provider_id}
- **Context Condition:** {att.context_condition.value}
- **Base Commit:** {ctx.base_commit}
- **Head Commit:** {ctx.head_commit}

---

{prompt}
"""
            filepath.write_text(header, encoding="utf-8")
            count += 1

            index_lines.append(
                f"| {idx} | **{att.case_id}** | `{att.provider_id}` | `{att.context_condition.value}` | `{att.batch_id}` | `{att.id}` | [{filename}]({filename}) |"
            )

        index_path = self.prompts_dir / "README.md"
        index_path.write_text("\n".join(index_lines), encoding="utf-8")
        return count

    def scan_and_match_reviews(
        self,
        pending_attempts: list,
        conn,
    ) -> list[IngestionCandidate]:
        """Scan reviews directory and match files to pending attempts with strict metadata verification."""
        if not self.reviews_dir.is_dir():
            return []

        candidates = []
        pending_by_id = {a.id: a for a in pending_attempts}

        # Multi-key index for fallback matching: (case_id, provider_id, context_condition) -> list of attempts
        pending_by_tuple = {}
        for a in pending_attempts:
            key = (a.case_id, a.provider_id, a.context_condition.value)
            pending_by_tuple.setdefault(key, []).append(a)

        for file_path in sorted(self.reviews_dir.glob("*.md")):
            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception as exc:
                candidates.append(
                    IngestionCandidate(
                        file_path=file_path,
                        attempt_id="",
                        batch_id="",
                        provider_id="",
                        case_id="",
                        context_condition="",
                        match_source="read_failure",
                        raw_content="",
                        content_hash_sha256="",
                        is_valid=False,
                        rejection_reason=f"Unreadable file: {exc}",
                    )
                )
                continue

            # Skip empty files or placeholders
            clean_content = self._strip_metadata_comment(content)
            if not clean_content or len(clean_content) < 50:
                continue  # Placeholder or empty file

            # Do not re-match files already recorded in database review_responses
            content_hash = hashlib.sha256(clean_content.encode("utf-8")).hexdigest()

            # Check if this hash is already in the database
            already_ingested = conn.execute(
                "SELECT count(*) FROM review_responses WHERE raw_content = ?",
                (clean_content,),
            ).fetchone()[0]
            if already_ingested > 0:
                continue  # Already ingested genuine review; preserve without re-triggering

            # Attempt Match Strategy 1: Explicit attempt_id in comment header
            att_id_match = re.search(r"attempt_id:\s*([a-zA-Z0-9_-]+)", content)
            if att_id_match:
                target_id = att_id_match.group(1).strip()
                target_att = pending_by_id.get(target_id)
                if target_att:
                    candidates.append(
                        IngestionCandidate(
                            file_path=file_path,
                            attempt_id=target_att.id,
                            batch_id=target_att.batch_id,
                            provider_id=target_att.provider_id,
                            case_id=target_att.case_id,
                            context_condition=target_att.context_condition.value,
                            match_source="header_attempt_id",
                            raw_content=clean_content,
                            content_hash_sha256=content_hash,
                            is_valid=True,
                        )
                    )
                    continue

            # Attempt Match Strategy 2: Explicit metadata in comment header
            meta_match = self._extract_header_metadata(content)
            if meta_match:
                c_id = meta_match.get("case_id")
                p_id = meta_match.get("provider_id")
                cond = meta_match.get("context_condition")
                key = (c_id, p_id, cond)
                matches = pending_by_tuple.get(key, [])
                if len(matches) == 1:
                    target_att = matches[0]
                    candidates.append(
                        IngestionCandidate(
                            file_path=file_path,
                            attempt_id=target_att.id,
                            batch_id=target_att.batch_id,
                            provider_id=target_att.provider_id,
                            case_id=target_att.case_id,
                            context_condition=target_att.context_condition.value,
                            match_source="header_metadata",
                            raw_content=clean_content,
                            content_hash_sha256=content_hash,
                            is_valid=True,
                        )
                    )
                    continue
                elif len(matches) > 1:
                    candidates.append(
                        IngestionCandidate(
                            file_path=file_path,
                            attempt_id="",
                            batch_id="",
                            provider_id=p_id or "",
                            case_id=c_id or "",
                            context_condition=cond or "",
                            match_source="ambiguous_header_metadata",
                            raw_content=clean_content,
                            content_hash_sha256=content_hash,
                            is_valid=False,
                            rejection_reason=f"Ambiguous match: multiple pending attempts match metadata {key}",
                        )
                    )
                    continue

            # Attempt Match Strategy 3: Deterministic filename matching (e.g. case-01_chatgpt_response.md)
            fn_match = self._match_by_structured_filename(file_path.name, pending_by_tuple)
            if fn_match:
                if len(fn_match) == 1:
                    target_att = fn_match[0]
                    candidates.append(
                        IngestionCandidate(
                            file_path=file_path,
                            attempt_id=target_att.id,
                            batch_id=target_att.batch_id,
                            provider_id=target_att.provider_id,
                            case_id=target_att.case_id,
                            context_condition=target_att.context_condition.value,
                            match_source="structured_filename",
                            raw_content=clean_content,
                            content_hash_sha256=content_hash,
                            is_valid=True,
                        )
                    )
                    continue
                else:
                    candidates.append(
                        IngestionCandidate(
                            file_path=file_path,
                            attempt_id="",
                            batch_id="",
                            provider_id="",
                            case_id="",
                            context_condition="",
                            match_source="ambiguous_filename",
                            raw_content=clean_content,
                            content_hash_sha256=content_hash,
                            is_valid=False,
                            rejection_reason=f"Ambiguous filename '{file_path.name}' matches {len(fn_match)} pending attempts",
                        )
                    )

        return candidates

    @staticmethod
    def _strip_metadata_comment(content: str) -> str:
        """Strip HTML comment block at beginning of review if present."""
        clean = re.sub(r"^\s*<!--[\s\S]*?-->\s*", "", content).strip()
        return clean

    @staticmethod
    def _extract_header_metadata(content: str) -> Optional[dict]:
        """Extract key-value metadata from top comment block."""
        match = re.search(r"<!--([\s\S]*?)-->", content)
        if not match:
            return None
        block = match.group(1)
        res = {}
        for line in block.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                res[k.strip()] = v.strip()
        return res if res else None

    @staticmethod
    def _match_by_structured_filename(filename: str, pending_by_tuple: dict) -> list:
        """Match filenames like case-03_chatgpt_response.md or case-04_snapshot_claude.md."""
        lower = filename.lower()

        # Find case number
        case_match = re.search(r"case[-_]?0?([1-8])", lower)
        if not case_match:
            return []
        case_id = f"case-{int(case_match.group(1)):02d}"

        # Find provider
        provider_id = None
        if "chatgpt" in lower:
            provider_id = "chatgpt-web"
        elif "claude" in lower:
            provider_id = "claude-web"

        if not provider_id:
            return []

        # Find context
        has_snapshot = "snapshot" in lower or "snap" in lower
        context_condition = (
            ContextCondition.CODE_AND_SNAPSHOT.value
            if has_snapshot
            else ContextCondition.CODE_ONLY.value
        )

        key = (case_id, provider_id, context_condition)
        return pending_by_tuple.get(key, [])

    @staticmethod
    def _resolve_model_name(provider_id: str) -> str:
        if "chatgpt" in provider_id:
            return "gpt-4o"
        elif "claude" in provider_id:
            return "claude-3-5-sonnet"
        return "unknown-model"
