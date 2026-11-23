"""Review response collection, normalization, and archival."""

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Optional

from benchmark.collector.storage import RawEvidenceStore
from benchmark.db.repositories import ResponseRepository
from benchmark.domain.models import ReviewAttempt, ReviewResponse
from benchmark.providers.base import ProviderRawResult


class ResponseValidationError(ValueError):
    """Raised when incoming review payload fails validation."""
    pass


class ReviewCollector:
    """Ingests raw provider results, normalizes metadata, and writes dual storage."""

    def __init__(
        self,
        response_repo: ResponseRepository,
        evidence_store: Optional[RawEvidenceStore] = None,
    ):
        self.response_repo = response_repo
        self.evidence_store = evidence_store or RawEvidenceStore()

    def collect(
        self,
        attempt: ReviewAttempt,
        result: ProviderRawResult,
    ) -> ReviewResponse:
        """Validate, normalize, and persist review response to database and disk mirror."""
        raw_text = result.raw_content
        if not raw_text or not raw_text.strip():
            raise ResponseValidationError(
                f"Provider returned empty review response for attempt {attempt.id}"
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        response_id = f"resp-{attempt.id}"
        content_clean = raw_text.strip()
        content_hash = hashlib.sha256(content_clean.encode("utf-8")).hexdigest()

        # 1. Normalize domain response record
        response = ReviewResponse(
            id=response_id,
            attempt_id=attempt.id,
            raw_content=content_clean,
            content_format="markdown",
            external_id=result.external_id,
            http_status=result.http_status,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            received_at=now_iso,
            execution_mode=getattr(result, "execution_mode", "live") or "live",
        )

        # 2. Persist in database
        self.response_repo.save(response)

        # 3. Mirror to filesystem store with provenance metadata
        metadata = {
            "response_id": response_id,
            "attempt_id": attempt.id,
            "batch_id": attempt.batch_id,
            "provider_id": attempt.provider_id,
            "case_id": attempt.case_id,
            "context_condition": attempt.context_condition.value,
            "model_name": result.model_name or attempt.model_name,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "duration_ms": result.duration_ms,
            "http_status": result.http_status,
            "finish_reason": result.finish_reason,
            "received_at": now_iso,
            "content_hash_sha256": content_hash,
            "execution_mode": response.execution_mode,
            "is_synthetic": response.execution_mode != "live",
        }
        self.evidence_store.save_evidence(
            batch_id=attempt.batch_id,
            attempt_id=attempt.id,
            content=response.raw_content,
            metadata=metadata,
        )

        return response
