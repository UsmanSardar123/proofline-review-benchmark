-- Benchmark Database Schema Migration 002
-- Records how each review response was produced so synthetic fixture/dry-run/mock
-- output can never be confused with a genuine external reviewer result.
-- Allowed values: 'live' (real API/CLI/manual paste), 'fixture', 'dry_run', 'mock'.

ALTER TABLE review_responses ADD COLUMN execution_mode TEXT NOT NULL DEFAULT 'live';

-- Backfill: responses produced by built-in offline fixtures carry deterministic
-- synthetic external IDs. Only the new column is set; no existing values change.
UPDATE review_responses SET execution_mode = 'fixture'
WHERE external_id LIKE 'cr-rev-%' OR external_id LIKE 'grep-rev-%';
UPDATE review_responses SET execution_mode = 'mock'
WHERE external_id LIKE 'mock-rev-%';
UPDATE review_responses SET execution_mode = 'dry_run'
WHERE external_id LIKE 'msg_claude_%' OR external_id LIKE 'chatcmpl_gpt_%';
