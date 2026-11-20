-- Benchmark Database Schema Migration 001
-- Target Database: benchmark.sqlite

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    scoring_protocol_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('draft', 'active', 'completed', 'archived')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_batches (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL REFERENCES experiments(id) ON DELETE RESTRICT,
    batch_name TEXT NOT NULL,
    planned_attempts_count INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'interrupted', 'failed')),
    started_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS providers (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    adapter_type TEXT NOT NULL CHECK(adapter_type IN ('cli', 'api_http', 'github_pr', 'mock')),
    default_model TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS benchmark_cases (
    id TEXT PRIMARY KEY,
    case_number INTEGER NOT NULL UNIQUE,
    title TEXT NOT NULL,
    pr_description TEXT NOT NULL,
    baseline_commit TEXT NOT NULL,
    target_commit TEXT NOT NULL,
    patch_relpath TEXT NOT NULL,
    has_deployment_snapshot INTEGER NOT NULL DEFAULT 0,
    snapshot_content TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ground_truth_defects (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES benchmark_cases(id) ON DELETE RESTRICT,
    defect_category TEXT NOT NULL CHECK(defect_category IN ('LOGIC_BUG', 'DEPLOYMENT_CONFLICT', 'CONFIG_LIMIT', 'DATA_INTEGRITY', 'REGRESSION', 'PERFORMANCE', 'CONTRACT_CHANGE')),
    description TEXT NOT NULL,
    target_file TEXT NOT NULL,
    target_lines TEXT,
    requires_snapshot INTEGER NOT NULL DEFAULT 0,
    expected_action TEXT NOT NULL DEFAULT 'BLOCK_PR' CHECK(expected_action IN ('BLOCK_PR', 'WARN', 'APPROVE'))
);

CREATE TABLE IF NOT EXISTS review_attempts (
    id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES execution_batches(id) ON DELETE RESTRICT,
    provider_id TEXT NOT NULL REFERENCES providers(id) ON DELETE RESTRICT,
    case_id TEXT NOT NULL REFERENCES benchmark_cases(id) ON DELETE RESTRICT,
    context_condition TEXT NOT NULL CHECK(context_condition IN ('CODE_ONLY', 'CODE_AND_SNAPSHOT')),
    attempt_type TEXT NOT NULL CHECK(attempt_type IN ('INITIAL', 'AUTOMATIC_RETRY', 'INTENTIONAL_REPEAT')),
    parent_attempt_id TEXT REFERENCES review_attempts(id) ON DELETE SET NULL,
    attempt_number INTEGER NOT NULL DEFAULT 1,
    retry_count INTEGER NOT NULL DEFAULT 0,
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK(status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'QUOTA_EXHAUSTED', 'CANCELLED')),
    model_name TEXT NOT NULL,
    settings_hash TEXT NOT NULL,
    base_commit TEXT NOT NULL,
    head_commit TEXT NOT NULL,
    error_reason TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    duration_ms INTEGER,
    UNIQUE (batch_id, provider_id, case_id, context_condition, attempt_number)
);

CREATE TABLE IF NOT EXISTS review_responses (
    id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL UNIQUE REFERENCES review_attempts(id) ON DELETE RESTRICT,
    raw_content TEXT NOT NULL,
    content_format TEXT NOT NULL DEFAULT 'markdown',
    external_id TEXT,
    http_status INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    received_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_findings (
    id TEXT PRIMARY KEY,
    response_id TEXT NOT NULL REFERENCES review_responses(id) ON DELETE RESTRICT,
    attempt_id TEXT NOT NULL REFERENCES review_attempts(id) ON DELETE RESTRICT,
    file_path TEXT,
    line_start INTEGER,
    line_end INTEGER,
    reported_severity TEXT,
    summary TEXT NOT NULL,
    raw_comment_slice TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS finding_evaluations (
    id TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL UNIQUE REFERENCES review_findings(id) ON DELETE RESTRICT,
    ground_truth_id TEXT REFERENCES ground_truth_defects(id) ON DELETE SET NULL,
    classification TEXT NOT NULL CHECK(classification IN ('TRUE_POSITIVE', 'FALSE_POSITIVE', 'VALID_UNEXPECTED', 'DUPLICATE')),
    cites_deployment_evidence INTEGER NOT NULL DEFAULT 0,
    evaluator_type TEXT NOT NULL DEFAULT 'rule_matcher',
    rationale TEXT,
    evaluated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attempt_scores (
    id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL UNIQUE REFERENCES review_attempts(id) ON DELETE RESTRICT,
    tp_count INTEGER NOT NULL DEFAULT 0,
    fp_count INTEGER NOT NULL DEFAULT 0,
    fn_count INTEGER NOT NULL DEFAULT 0,
    vuf_count INTEGER NOT NULL DEFAULT 0,
    precision_rate REAL,
    recall_rate REAL,
    f1_metric REAL,
    passed_cleanly INTEGER NOT NULL DEFAULT 0,
    computed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS run_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT REFERENCES execution_batches(id) ON DELETE CASCADE,
    attempt_id TEXT REFERENCES review_attempts(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT,
    message TEXT NOT NULL,
    details_json TEXT,
    created_at TEXT NOT NULL
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_attempts_batch_status ON review_attempts (batch_id, status);
CREATE INDEX IF NOT EXISTS idx_attempts_lookup ON review_attempts (provider_id, case_id, context_condition);
CREATE INDEX IF NOT EXISTS idx_findings_attempt ON review_findings (attempt_id);
CREATE INDEX IF NOT EXISTS idx_events_attempt ON run_events (attempt_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ground_truth_case ON ground_truth_defects (case_id);
