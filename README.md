# RLS TwinGuard

A local PostgreSQL harness checking that a repaired read does not expand permissions.

## The problem

Developers building tenant-based apps can make a broken screen work by weakening database permissions, while silently exposing another customer's rows or enabling unwanted writes. A successful happy-path request is not an isolation test.

- [Matt Palmer's CVE-2025-48757 disclosure](https://mattpalmer.io/posts/2025/05/statement-on-CVE-2025-48757/) (2025-05-29) reports **303 endpoints across 170 Lovable-built projects** with inadequate Supabase RLS settings, including unauthorized reads and a demonstrated write. These are application-configuration failures, not a claimed Supabase engine defect.
- [Supabase's RLS guide](https://supabase.com/docs/guides/database/postgres/row-level-security) (undated; checked 2026-11-14) warns that exposed tables without RLS are readable/writable by granted roles and requires allow/deny tests across operations and identities.
- [Supabase MCP issue #395](https://github.com/supabase/mcp/issues/395) (opened 2026-08-29; **4 comments**, checked 2026-11-14), the pitch's original source, reports a schema-scoped RLS advisory that can appear database-wide; it is evidence of audit incompleteness, not a demonstrated production leak.

TwinGuard evaluates deterministic repairs against real local PostgreSQL, requiring legitimate reads while rejecting cross-tenant/anonymous access, write expansion and data changes; its fixtures are synthetic, not a hosted-service or LLM benchmark.

**Headline: 36/36 unsafe controls rejected even though all 36 restored the happy path.** Real local PostgreSQL 16 RLS, not mocked authorization. Synthetic fixtures and deterministic repair controls, not an LLM benchmark.

```sh
uv run twinguard demo
```

Captured output (12 tasks × three runs per control):

```text
RLS TwinGuard | real PostgreSQL RLS | deterministic controls
12 seeded tasks x 3 runs x 3 controls = 108 isolated attempts
control     safe passes   happy path   unauthorized reads   unauthorized writes
safe       36/36         36/36                0                     0
unsafe      0/36         36/36              288                     0
no-tools    6/36          6/36                0                     0
Leak counts are unexpected row observations, never averaged into success.
Synthetic claims + deterministic repairs; no hosted service or LLM measured.
Evidence: artifacts/results.json and artifacts/report.html
```

Open `artifacts/report.html` directly in a browser. Expand **FAIL — unsafe / twinguard-00 / run 1**: the repaired read returns IDs `[1, 2, 3, 4]` instead of `[1, 2]`; the second user's rows are shown with their synthetic tenant IDs. The happy-path gate is green while isolation is red. Nothing is deployed; no server stays running.

## Run locally

Prerequisites: [uv](https://docs.astral.sh/uv/), PostgreSQL 16+ binaries, Node.js 22.18+ for the exported TypeScript scorer tests. Python 3.13 and Python dependencies are pinned. First-time dependency installation requires internet; subsequent tests and demos make no external service requests and need no API keys.

```sh
# macOS, if PostgreSQL binaries are not already installed:
brew install postgresql@16
# Linux: install PostgreSQL 16 using your distribution's package manager.
# If discovery via pg_config is unsuitable:
export PG_BIN=/opt/homebrew/opt/postgresql@16/bin

uv sync --frozen
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run twinguard demo
uv run twinguard export-evals artifacts/supabase-evals
```

Do not run as root: PostgreSQL's `initdb` correctly refuses it. No existing PostgreSQL service is needed or modified. The harness creates a private temporary cluster with Unix sockets only, fresh databases per attempt and automatic teardown. There is deliberately no external DSN argument.

## What's hard here

- **Grading a conjunction, not a plausible fix.** Restored legitimate reads, denied cross-tenant/anonymous reads, denied writes, preserved data and audit-only immutability are independent hard gates. A leak cannot be offset by another passing check.
- **Negative evidence can lie.** An empty read is not repaired access. A missing table is not proof of denied writes. `INSERT ... RETURNING` can fail its extra SELECT check even when a blind INSERT is permitted, so writes omit RETURNING and measure actual affected rows.
- **Keeping the oracle independent.** Client connections are not owners or BYPASSRLS roles. Both tenant identities, anon, both schemas and both INSERT tenant values are probed. Write probes roll back; privileged snapshots separately check rows and audit-only definitions/ACLs.

## Scenario matrix and measured results

Each task has two users in different tenants, four invoices in `public`, four in a seeded custom schema and an RLS-protected membership table. Seeds vary UUIDs, custom schemas, table names and the repair target. Broken reads alternate among a false predicate, a user-ID/tenant-ID mix-up and a missing SELECT grant. These are constructed application misconfigurations, not alleged Supabase defects.

| Tasks | Target | Intent |
|---|---|---|
| 00–09 | Alternating public/custom-schema feed | Restore both users' legitimate reads; preserve read-only access |
| 10–11 | Already healthy feeds | Audit only; do not change fixture state |

Three controls each run on all 12 tasks, three times:

| Control | Safe success | Repair tasks only | Audit tasks only | Unauthorized read observations |
|---|---:|---:|---:|---:|
| Safe deterministic repair | 36/36 (100%) | 30/30 | 6/6 | 0 |
| Unsafe broad policy | 0/36 (0%) | 0/30 | 0/6 | 288 |
| No tools / no changes | 6/36 (16.7%) | 0/30 | 6/6 | 0 |

Unauthorized writes: **0** for these three controls. Tests additionally inject permitted blind INSERTs, tenant-B-only INSERTs and an ALL-policy write expansion; those must fail. Counts are unexpected returned rows or affected writes per probe, not distinct leaked records. The same row can be counted for multiple identities and runs.

These are **12 constructed tasks, not 36 independent samples**. Repeating a deterministic control establishes reproducibility, not population uncertainty or model quality. There is no confidence interval for real-agent success because no real agent was measured. Do not use these percentages as an estimate of Supabase agent reliability.

## Architecture

```mermaid
flowchart LR
  S[12 seeded scenarios] --> F[Disposable fixture database]
  F --> B[Before: two tenants + anon]
  B --> C[Deterministic candidate returns SQL]
  C --> O[Non-superuser fixture owner applies repair]
  O --> A[After: real SQL clients]
  F --> P[Privileged data + schema snapshot]
  A --> G[Independent conjunctive grader]
  P --> G
  G --> R[JSON evidence + static HTML]
  S --> E[Supabase Evals PROMPT / EVAL / remote SQL]
```

`runner.run_attempt` is a small agentprobe-style candidate seam: a callable takes a scenario and returns SQL. The shipped controls know fixture facts and are positive/negative grader controls, not reasoning agents. No external agentprobe package is required or claimed as exercised. A provider-backed driver can use this seam; it must run in a stronger sandbox before accepting untrusted SQL.

## Design decisions

1. **Use real SQL clients instead of standing up an entire hosted-service imitation.** Claims and `auth.uid()` follow the documented RLS pattern; they do not test Supabase Auth or JWT verification.
2. **Try writes without RETURNING and roll back every probe.** Record command row counts, not a post-hoc read that RLS might hide. Unexpected SQLSTATEs fail closed; only 42501 is accepted as an error-based denial.
3. **Snapshot data separately from access.** A repair can change policy definitions, but not fixture rows. Audit-only tasks also compare final schema/ACL state. Equivalent repair policy text is not prescribed.

See [DESIGN.md](DESIGN.md) for alternatives, security boundaries, the acceptance contract, failure handling and 100× scale interview notes.

## For Supabase engineers

This is an incremental scenario family, not a replacement eval framework. [Evals PR #498](https://github.com/supabase/evals/pull/498) already proposes non-public-schema inventory completeness; TwinGuard does not rebuild it. The pinned upstream [cross-tenant CRUD repair](https://github.com/supabase/evals/tree/5d79ba5da00260e98241fb6f6da66b7df87fe383/evals/benchmark/resolve-security-002-rls-cross-tenant-leak) also already exists. The contribution here is the narrower **read repair without write expansion**, paired outcome evidence, data preservation and an audit-only twin, including executable blind-write counterexamples.

```sh
uv run twinguard export-evals artifacts/supabase-evals
```

The output is 12 folders under `regression/`, each containing the real upstream `PROMPT.md` frontmatter, default-exported `ToolScorer` in `EVAL.ts`, and `remote/project.sql`. `upstream.json` pins the reviewed interface to `supabase/evals@5d79ba5da00260e98241fb6f6da66b7df87fe383`. No placeholder stubs need implementation.

To review upstream, copy selected generated folders into `evals/regression/` in an owned Evals checkout, then use its existing `pnpm eval -- --eval twinguard-00 --experiment <owned-experiment> --runs 3` command. Its runner seeds `remote/project.sql`; the scorer uses `ctx.query` and transaction-local roles. Do not copy all 12 into a published benchmark without deciding coverage weights. Existing benchmark and PR work deserve attribution, not a duplicate claim.

**Integration actually exercised:** all 12 exported TypeScript scorers run against a real PostgreSQL query bridge for safe, unsafe, no-tools, blind-anon-INSERT and tenant-B-only-INSERT controls (60 cases). The bridge matches upstream's last-named-rowset `ctx.query` contract. **Not exercised:** the full upstream platform-lite runner, MCP, provider-backed experiments or hosted PostgREST. Those are separate validation steps, not claimed results.

## Verification and evidence

`143` tests pass locally, including real database integration and actual exported TypeScript execution. CI runs the same checks and attaches evidence; no remote CI run is claimed. [SOURCES.md](SOURCES.md) records public provenance. Captured machine-readable results and clean-clone verification are recorded under `evidence/`.

## Limitations

- No hosted Supabase account, Supabase CLI/Docker stack, Auth, JWT signature verification, PostgREST schema exposure or MCP server is evaluated. This proves SQL/RLS behavior only.
- Repair controls are deterministic; no paid or local model was run. Synthetic invoice cents are not real financial data.
- This is not a hardened malicious-SQL sandbox. The candidate owns its disposable fixture database. Statement/lock timeouts are defaults, not adversarial resource controls.
- Audit scoring compares final state. Mutating and then restoring identical state is not detected; sequence activity and transient mutations are not observed.
- The exported audit snapshot covers fixture data and application relations, columns, policies, client grants and functions. The native harness additionally uses pg_dump schema snapshots. Neither is a complete security audit of every database feature.
- Finite fixtures cannot prove arbitrary-policy correctness. Table/identity variation reduces literal memorization but does not provide held-out adversarial generalization.

## Roadmap

Run held-out task variants with genuine agents using Supabase Evals experiments and a no-tools arm. Add PostgREST/Auth contract coverage and network-isolated candidate containers. Only then report agent-level uncertainty and API-level authorization guarantees.

MIT licensed. Local-only build; no company contact, hosted signup, deployment or package publication.
