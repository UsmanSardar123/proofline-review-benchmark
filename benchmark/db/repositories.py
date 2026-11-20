"""Database access and repository layer for benchmark.sqlite."""

from datetime import datetime, timezone
import json
import sqlite3
from typing import Optional

from benchmark.domain.enums import AttemptStatus, AttemptType, ContextCondition
from benchmark.domain.models import (
    BenchmarkCase,
    ExecutionBatch,
    Experiment,
    Provider,
    ReviewAttempt,
    ReviewResponse,
    RunEvent,
)


class BaseRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db


class ExperimentRepository(BaseRepository):
    def create(self, experiment: Experiment) -> Experiment:
        query = """
            INSERT INTO experiments (id, name, description, scoring_protocol_version, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        self.db.execute(
            query,
            (
                experiment.id,
                experiment.name,
                experiment.description,
                experiment.scoring_protocol_version,
                experiment.status,
                experiment.created_at,
            ),
        )
        return experiment

    def get_by_id(self, experiment_id: str) -> Optional[Experiment]:
        query = "SELECT * FROM experiments WHERE id = ?"
        row = self.db.execute(query, (experiment_id,)).fetchone()
        if not row:
            return None
        return Experiment(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            scoring_protocol_version=row["scoring_protocol_version"],
            status=row["status"],
            created_at=row["created_at"],
        )

    def list_all(self) -> list[Experiment]:
        query = "SELECT * FROM experiments ORDER BY created_at DESC"
        rows = self.db.execute(query).fetchall()
        return [
            Experiment(
                id=r["id"],
                name=r["name"],
                description=r["description"],
                scoring_protocol_version=r["scoring_protocol_version"],
                status=r["status"],
                created_at=r["created_at"],
            )
            for r in rows
        ]


class BatchRepository(BaseRepository):
    def create(self, batch: ExecutionBatch) -> ExecutionBatch:
        query = """
            INSERT INTO execution_batches (id, experiment_id, batch_name, planned_attempts_count, status, started_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        self.db.execute(
            query,
            (
                batch.id,
                batch.experiment_id,
                batch.batch_name,
                batch.planned_attempts_count,
                batch.status,
                batch.started_at,
                batch.completed_at,
            ),
        )
        return batch

    def get_by_id(self, batch_id: str) -> Optional[ExecutionBatch]:
        query = "SELECT * FROM execution_batches WHERE id = ?"
        row = self.db.execute(query, (batch_id,)).fetchone()
        if not row:
            return None
        return ExecutionBatch(
            id=row["id"],
            experiment_id=row["experiment_id"],
            batch_name=row["batch_name"],
            planned_attempts_count=row["planned_attempts_count"],
            status=row["status"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )

    def update_status(self, batch_id: str, status: str, completed_at: Optional[str] = None) -> None:
        if completed_at:
            self.db.execute(
                "UPDATE execution_batches SET status = ?, completed_at = ? WHERE id = ?",
                (status, completed_at, batch_id),
            )
        else:
            self.db.execute(
                "UPDATE execution_batches SET status = ? WHERE id = ?",
                (status, batch_id),
            )

    def list_for_experiment(self, experiment_id: str) -> list[ExecutionBatch]:
        query = "SELECT * FROM execution_batches WHERE experiment_id = ? ORDER BY started_at DESC"
        rows = self.db.execute(query, (experiment_id,)).fetchall()
        return [
            ExecutionBatch(
                id=r["id"],
                experiment_id=r["experiment_id"],
                batch_name=r["batch_name"],
                planned_attempts_count=r["planned_attempts_count"],
                status=r["status"],
                started_at=r["started_at"],
                completed_at=r["completed_at"],
            )
            for r in rows
        ]


class ProviderRepository(BaseRepository):
    def register(self, provider: Provider) -> Provider:
        query = """
            INSERT INTO providers (id, display_name, adapter_type, default_model, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                display_name=excluded.display_name,
                adapter_type=excluded.adapter_type,
                default_model=excluded.default_model,
                is_active=excluded.is_active
        """
        self.db.execute(
            query,
            (
                provider.id,
                provider.display_name,
                provider.adapter_type,
                provider.default_model,
                1 if provider.is_active else 0,
                provider.created_at,
            ),
        )
        return provider

    def get_by_id(self, provider_id: str) -> Optional[Provider]:
        query = "SELECT * FROM providers WHERE id = ?"
        row = self.db.execute(query, (provider_id,)).fetchone()
        if not row:
            return None
        return Provider(
            id=row["id"],
            display_name=row["display_name"],
            adapter_type=row["adapter_type"],
            default_model=row["default_model"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
        )

    def list_active(self) -> list[Provider]:
        query = "SELECT * FROM providers WHERE is_active = 1 ORDER BY id"
        rows = self.db.execute(query).fetchall()
        return [
            Provider(
                id=r["id"],
                display_name=r["display_name"],
                adapter_type=r["adapter_type"],
                default_model=r["default_model"],
                is_active=bool(r["is_active"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]


class CaseRepository(BaseRepository):
    def register(self, case: BenchmarkCase) -> BenchmarkCase:
        query = """
            INSERT INTO benchmark_cases (
                id, case_number, title, pr_description, baseline_commit, target_commit,
                patch_relpath, has_deployment_snapshot, snapshot_content, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                case_number=excluded.case_number,
                title=excluded.title,
                pr_description=excluded.pr_description,
                baseline_commit=excluded.baseline_commit,
                target_commit=excluded.target_commit,
                patch_relpath=excluded.patch_relpath,
                has_deployment_snapshot=excluded.has_deployment_snapshot,
                snapshot_content=excluded.snapshot_content
        """
        self.db.execute(
            query,
            (
                case.id,
                case.case_number,
                case.title,
                case.pr_description,
                case.baseline_commit,
                case.target_commit,
                case.patch_relpath,
                1 if case.has_deployment_snapshot else 0,
                case.snapshot_content,
                case.created_at,
            ),
        )
        return case

    def get_by_id(self, case_id: str) -> Optional[BenchmarkCase]:
        query = "SELECT * FROM benchmark_cases WHERE id = ?"
        row = self.db.execute(query, (case_id,)).fetchone()
        if not row:
            return None
        return BenchmarkCase(
            id=row["id"],
            case_number=row["case_number"],
            title=row["title"],
            pr_description=row["pr_description"],
            baseline_commit=row["baseline_commit"],
            target_commit=row["target_commit"],
            patch_relpath=row["patch_relpath"],
            has_deployment_snapshot=bool(row["has_deployment_snapshot"]),
            snapshot_content=row["snapshot_content"],
            created_at=row["created_at"],
        )

    def get_by_number(self, case_number: int) -> Optional[BenchmarkCase]:
        query = "SELECT * FROM benchmark_cases WHERE case_number = ?"
        row = self.db.execute(query, (case_number,)).fetchone()
        if not row:
            return None
        return BenchmarkCase(
            id=row["id"],
            case_number=row["case_number"],
            title=row["title"],
            pr_description=row["pr_description"],
            baseline_commit=row["baseline_commit"],
            target_commit=row["target_commit"],
            patch_relpath=row["patch_relpath"],
            has_deployment_snapshot=bool(row["has_deployment_snapshot"]),
            snapshot_content=row["snapshot_content"],
            created_at=row["created_at"],
        )

    def list_all(self) -> list[BenchmarkCase]:
        query = "SELECT * FROM benchmark_cases ORDER BY case_number ASC"
        rows = self.db.execute(query).fetchall()
        return [
            BenchmarkCase(
                id=r["id"],
                case_number=r["case_number"],
                title=r["title"],
                pr_description=r["pr_description"],
                baseline_commit=r["baseline_commit"],
                target_commit=r["target_commit"],
                patch_relpath=r["patch_relpath"],
                has_deployment_snapshot=bool(r["has_deployment_snapshot"]),
                snapshot_content=r["snapshot_content"],
                created_at=r["created_at"],
            )
            for r in rows
        ]


class AttemptRepository(BaseRepository):
    def _row_to_attempt(self, row: sqlite3.Row) -> ReviewAttempt:
        return ReviewAttempt(
            id=row["id"],
            batch_id=row["batch_id"],
            provider_id=row["provider_id"],
            case_id=row["case_id"],
            context_condition=ContextCondition(row["context_condition"]),
            attempt_type=AttemptType(row["attempt_type"]),
            parent_attempt_id=row["parent_attempt_id"],
            attempt_number=row["attempt_number"],
            retry_count=row["retry_count"],
            idempotency_key=row["idempotency_key"],
            status=AttemptStatus(row["status"]),
            model_name=row["model_name"],
            settings_hash=row["settings_hash"],
            base_commit=row["base_commit"],
            head_commit=row["head_commit"],
            error_reason=row["error_reason"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            duration_ms=row["duration_ms"],
        )

    def create(self, attempt: ReviewAttempt) -> ReviewAttempt:
        query = """
            INSERT INTO review_attempts (
                id, batch_id, provider_id, case_id, context_condition, attempt_type,
                parent_attempt_id, attempt_number, retry_count, idempotency_key, status,
                model_name, settings_hash, base_commit, head_commit, error_reason,
                created_at, started_at, completed_at, duration_ms
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.db.execute(
            query,
            (
                attempt.id,
                attempt.batch_id,
                attempt.provider_id,
                attempt.case_id,
                attempt.context_condition.value,
                attempt.attempt_type.value,
                attempt.parent_attempt_id,
                attempt.attempt_number,
                attempt.retry_count,
                attempt.idempotency_key,
                attempt.status.value,
                attempt.model_name,
                attempt.settings_hash,
                attempt.base_commit,
                attempt.head_commit,
                attempt.error_reason,
                attempt.created_at,
                attempt.started_at,
                attempt.completed_at,
                attempt.duration_ms,
            ),
        )
        return attempt

    def get_by_id(self, attempt_id: str) -> Optional[ReviewAttempt]:
        query = "SELECT * FROM review_attempts WHERE id = ?"
        row = self.db.execute(query, (attempt_id,)).fetchone()
        return self._row_to_attempt(row) if row else None

    def get_by_idempotency_key(self, key: str) -> Optional[ReviewAttempt]:
        query = "SELECT * FROM review_attempts WHERE idempotency_key = ?"
        row = self.db.execute(query, (key,)).fetchone()
        return self._row_to_attempt(row) if row else None

    def list_for_batch(self, batch_id: str) -> list[ReviewAttempt]:
        query = "SELECT * FROM review_attempts WHERE batch_id = ? ORDER BY case_id, provider_id, attempt_number"
        rows = self.db.execute(query, (batch_id,)).fetchall()
        return [self._row_to_attempt(r) for r in rows]

    def list_by_status(self, batch_id: str, statuses: list[AttemptStatus]) -> list[ReviewAttempt]:
        placeholders = ",".join("?" for _ in statuses)
        query = f"SELECT * FROM review_attempts WHERE batch_id = ? AND status IN ({placeholders}) ORDER BY created_at"
        params = [batch_id, *[s.value for s in statuses]]
        rows = self.db.execute(query, params).fetchall()
        return [self._row_to_attempt(r) for r in rows]

    def update_status(self, attempt_id: str, status: AttemptStatus, error_reason: Optional[str] = None) -> None:
        self.db.execute(
            "UPDATE review_attempts SET status = ?, error_reason = ? WHERE id = ?",
            (status.value, error_reason, attempt_id),
        )

    def mark_running(self, attempt_id: str, started_at: Optional[str] = None) -> None:
        ts = started_at or datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "UPDATE review_attempts SET status = ?, started_at = ? WHERE id = ?",
            (AttemptStatus.RUNNING.value, ts, attempt_id),
        )

    def mark_completed(self, attempt_id: str, completed_at: Optional[str] = None, duration_ms: Optional[int] = None) -> None:
        ts = completed_at or datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "UPDATE review_attempts SET status = ?, completed_at = ?, duration_ms = ? WHERE id = ?",
            (AttemptStatus.COMPLETED.value, ts, duration_ms, attempt_id),
        )

    def mark_failed(self, attempt_id: str, error_reason: str, completed_at: Optional[str] = None) -> None:
        ts = completed_at or datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "UPDATE review_attempts SET status = ?, completed_at = ?, error_reason = ? WHERE id = ?",
            (AttemptStatus.FAILED.value, ts, error_reason, attempt_id),
        )

    def mark_quota_exhausted(self, attempt_id: str, reason: str) -> None:
        self.db.execute(
            "UPDATE review_attempts SET status = ?, error_reason = ? WHERE id = ?",
            (AttemptStatus.QUOTA_EXHAUSTED.value, reason, attempt_id),
        )

    def increment_retry(self, attempt_id: str) -> None:
        self.db.execute(
            "UPDATE review_attempts SET retry_count = retry_count + 1, attempt_type = ? WHERE id = ?",
            (AttemptType.AUTOMATIC_RETRY.value, attempt_id),
        )


class ResponseRepository(BaseRepository):
    def save(self, response: ReviewResponse) -> ReviewResponse:
        query = """
            INSERT INTO review_responses (
                id, attempt_id, raw_content, content_format, external_id,
                http_status, prompt_tokens, completion_tokens, received_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.db.execute(
            query,
            (
                response.id,
                response.attempt_id,
                response.raw_content,
                response.content_format,
                response.external_id,
                response.http_status,
                response.prompt_tokens,
                response.completion_tokens,
                response.received_at,
            ),
        )
        return response

    def get_by_attempt_id(self, attempt_id: str) -> Optional[ReviewResponse]:
        query = "SELECT * FROM review_responses WHERE attempt_id = ?"
        row = self.db.execute(query, (attempt_id,)).fetchone()
        if not row:
            return None
        return ReviewResponse(
            id=row["id"],
            attempt_id=row["attempt_id"],
            raw_content=row["raw_content"],
            content_format=row["content_format"],
            external_id=row["external_id"],
            http_status=row["http_status"],
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            received_at=row["received_at"],
        )


class RunEventRepository(BaseRepository):
    def log(self, event: RunEvent) -> RunEvent:
        query = """
            INSERT INTO run_events (batch_id, attempt_id, event_type, from_state, to_state, message, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor = self.db.execute(
            query,
            (
                event.batch_id,
                event.attempt_id,
                event.event_type,
                event.from_state,
                event.to_state,
                event.message,
                event.details_json,
                event.created_at,
            ),
        )
        event.id = cursor.lastrowid
        return event

    def list_for_attempt(self, attempt_id: str) -> list[RunEvent]:
        query = "SELECT * FROM run_events WHERE attempt_id = ? ORDER BY id ASC"
        rows = self.db.execute(query, (attempt_id,)).fetchall()
        return [
            RunEvent(
                id=r["id"],
                batch_id=r["batch_id"],
                attempt_id=r["attempt_id"],
                event_type=r["event_type"],
                from_state=r["from_state"],
                to_state=r["to_state"],
                message=r["message"],
                details_json=r["details_json"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def list_for_batch(self, batch_id: str) -> list[RunEvent]:
        query = "SELECT * FROM run_events WHERE batch_id = ? ORDER BY id ASC"
        rows = self.db.execute(query, (batch_id,)).fetchall()
        return [
            RunEvent(
                id=r["id"],
                batch_id=r["batch_id"],
                attempt_id=r["attempt_id"],
                event_type=r["event_type"],
                from_state=r["from_state"],
                to_state=r["to_state"],
                message=r["message"],
                details_json=r["details_json"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
