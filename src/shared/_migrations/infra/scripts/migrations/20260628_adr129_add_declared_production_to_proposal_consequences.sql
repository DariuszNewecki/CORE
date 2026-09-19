-- ADR-129 D2: persist the declared production set alongside files_changed.
-- declared_production is the union of _sandbox_target_paths (observed by
-- SandboxLifecycle) and files_produced (declared by the action) — the same
-- set that drives commit_paths. Storing it enables CommitAuthorshipAuditWorker
-- to compare actual diff against the production claim post-commit.
--
-- Pre-existing rows default to '[]' (empty array), which the worker treats
-- as "unverifiable" and skips rather than false-positiving on old history.

ALTER TABLE core.proposal_consequences
    ADD COLUMN IF NOT EXISTS declared_production jsonb DEFAULT '[]'::jsonb NOT NULL;
