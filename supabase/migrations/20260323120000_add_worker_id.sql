-- Session 3: Instance-aware startup recovery
-- Adds worker_id column to api_tasks for multi-worker scoped recovery.
-- Existing rows get NULL (claimed by the first worker to start).
ALTER TABLE api_tasks ADD COLUMN IF NOT EXISTS worker_id TEXT;
CREATE INDEX IF NOT EXISTS ix_api_tasks_worker_id ON api_tasks (worker_id);
