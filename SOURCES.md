# Public sources and boundaries

Reviewed 2026-11-13. No employer source, prompts, records or credentials were used. All fixtures and candidate controls were authored for this project. No upstream source is vendored.

- [Supabase RLS guide](https://supabase.com/docs/guides/database/postgres/row-level-security): grants versus policies, `authenticated`/`anon`, `auth.uid()`, and allow/deny tests per operation. This is the direct motivation for the repair acceptance contract.
- [MCP issue #395](https://github.com/supabase/mcp/issues/395): still open when checked. The reporter describes a scoped table advisory; this demo does not claim to reproduce or fix that MCP issue.
- [Evals PR #498](https://github.com/supabase/evals/pull/498): still open when checked. Its non-public-schema inventory scenario is already proposed and is not reproduced here.
- [Supabase Evals](https://github.com/supabase/evals/tree/5d79ba5da00260e98241fb6f6da66b7df87fe383): pinned public interface reference. `PROMPT.md` metadata, `ToolScorer`, `ctx.query` and the last-named-rowset result convention were inspected. The generated pack follows these contracts.
- [Existing cross-tenant repair](https://github.com/supabase/evals/tree/5d79ba5da00260e98241fb6f6da66b7df87fe383/evals/benchmark/resolve-security-002-rls-cross-tenant-leak): already grades CRUD repair. TwinGuard is narrower: restore a read-only feed, forbid permission expansion, preserve fixture data and compare audit-only state. It does not claim cross-tenant repair evals are new to Supabase.
- [Existing SQL role probes](https://github.com/supabase/evals/blob/5d79ba5da00260e98241fb6f6da66b7df87fe383/evals/benchmark/build-rls-003-org-roles-permissions/EVAL.ts): documents using rolled-back SQL identities when transactional API behavior is unavailable. TwinGuard independently implements this public technique.

Runtime dependencies: psycopg/psycopg-binary (LGPL-3.0 with linking exception); PostgreSQL (PostgreSQL License). Development dependencies and transitive versions are locked in `uv.lock`. Supabase Evals is an interface/reference, not a runtime dependency. No paid model, hosted Supabase, CLI, MCP or Docker dependency is required for the local demo.
