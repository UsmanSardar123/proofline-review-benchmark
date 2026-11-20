"""Domain data models and value objects for the benchmark engine."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from typing import Optional

from benchmark.domain.enums import (
    AttemptStatus,
    AttemptType,
    ContextCondition,
    DefectCategory,
    EvaluationClass,
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Experiment:
    id: str
    name: str
    scoring_protocol_version: str
    status: str = "active"
    description: Optional[str] = None
    created_at: str = field(default_factory=now_utc_iso)


@dataclass
class ExecutionBatch:
    id: str
    experiment_id: str
    batch_name: str
    planned_attempts_count: int
    status: str = "pending"
    started_at: str = field(default_factory=now_utc_iso)
    completed_at: Optional[str] = None


@dataclass
class Provider:
    id: str
    display_name: str
    adapter_type: str
    default_model: str
    is_active: bool = True
    created_at: str = field(default_factory=now_utc_iso)


@dataclass
class BenchmarkCase:
    id: str
    case_number: int
    title: str
    pr_description: str
    baseline_commit: str
    target_commit: str
    patch_relpath: str
    has_deployment_snapshot: bool = False
    snapshot_content: Optional[str] = None
    created_at: str = field(default_factory=now_utc_iso)


@dataclass
class GroundTruthDefect:
    id: str
    case_id: str
    defect_category: DefectCategory
    description: str
    target_file: str
    target_lines: Optional[str] = None
    requires_snapshot: bool = False
    expected_action: str = "BLOCK_PR"


@dataclass
class ReviewAttempt:
    id: str
    batch_id: str
    provider_id: str
    case_id: str
    context_condition: ContextCondition
    model_name: str
    settings_hash: str
    base_commit: str
    head_commit: str
    attempt_type: AttemptType = AttemptType.INITIAL
    parent_attempt_id: Optional[str] = None
    attempt_number: int = 1
    retry_count: int = 0
    idempotency_key: str = ""
    status: AttemptStatus = AttemptStatus.PENDING
    error_reason: Optional[str] = None
    created_at: str = field(default_factory=now_utc_iso)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None

    def __post_init__(self):
        if not self.idempotency_key:
            data = f"{self.batch_id}:{self.provider_id}:{self.case_id}:{self.context_condition.value}:{self.attempt_number}"
            self.idempotency_key = hashlib.sha256(data.encode("utf-8")).hexdigest()


@dataclass
class ReviewResponse:
    id: str
    attempt_id: str
    raw_content: str
    content_format: str = "markdown"
    external_id: Optional[str] = None
    http_status: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    received_at: str = field(default_factory=now_utc_iso)


@dataclass
class ReviewFinding:
    id: str
    response_id: str
    attempt_id: str
    summary: str
    file_path: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    reported_severity: Optional[str] = None
    raw_comment_slice: Optional[str] = None
    created_at: str = field(default_factory=now_utc_iso)


@dataclass
class FindingEvaluation:
    id: str
    finding_id: str
    classification: EvaluationClass
    ground_truth_id: Optional[str] = None
    cites_deployment_evidence: bool = False
    evaluator_type: str = "rule_matcher"
    rationale: Optional[str] = None
    evaluated_at: str = field(default_factory=now_utc_iso)


@dataclass
class AttemptScore:
    id: str
    attempt_id: str
    tp_count: int = 0
    fp_count: int = 0
    fn_count: int = 0
    vuf_count: int = 0
    precision_rate: Optional[float] = None
    recall_rate: Optional[float] = None
    f1_metric: Optional[float] = None
    passed_cleanly: bool = False
    computed_at: str = field(default_factory=now_utc_iso)


@dataclass
class RunEvent:
    event_type: str
    message: str
    id: Optional[int] = None
    batch_id: Optional[str] = None
    attempt_id: Optional[str] = None
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    details_json: Optional[str] = None
    created_at: str = field(default_factory=now_utc_iso)
