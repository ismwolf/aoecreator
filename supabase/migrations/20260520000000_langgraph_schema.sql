-- Faz 3 C.2 — LangGraph checkpoint schema
-- AsyncPostgresSaver creates its own tables (checkpoints, checkpoint_blobs,
-- checkpoint_writes) in this schema via .setup() at runtime. We only create
-- the schema + grants — drift-safe per LangGraph 0.6 docs.

create schema if not exists langgraph;

-- service_role bypasses RLS, so it can write to any schema.
-- We don't grant authenticated/anon — checkpoint tables are framework infra,
-- never read directly from app/UI.
grant usage on schema langgraph to postgres, service_role;
grant create on schema langgraph to service_role;  -- so .setup() can CREATE TABLE
