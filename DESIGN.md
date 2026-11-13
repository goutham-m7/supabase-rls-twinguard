# RLS TwinGuard design and interview notes

## Problem and scope

A repair can restore a legitimate invoice read while expanding permissions. Grade the conjunction of restored access, tenant isolation, denied writes, preserved data, and audit-only immutability. This is not an RLS inventory scanner or a claim about a Supabase vulnerability. All records are authored synthetic fixtures.

The public reference is Supabase Evals at `5d79ba5da00260e98241fb6f6da66b7df87fe383` (reviewed 2026-11-13). Its existing `resolve-security-002-rls-cross-tenant-leak` grades a full CRUD repair; this pack instead repairs broken reads without granting writes, adds paired before/after evidence and audit-only state preservation. PR #498 already covers non-public-schema inventory: https://github.com/supabase/evals/pull/498.

## Three hardest decisions

1. **Real authorization, deterministic candidate.** Run PostgreSQL 16 in a private temporary cluster, without TCP listeners. Separate SQL connections log in as `authenticated`, `anon`, or a non-superuser fixture owner. Supply synthetic request claims at the trusted client boundary. Reject simulated authorization, privileged read probes, and an LLM-dependent demo. The model boundary is a callable returning SQL; the shipped good/bad/no-tools controls are not AI performance measurements. No Supabase Auth, JWT verification, PostgREST, MCP, or hosted API is claimed.
2. **Behavior plus state, not policy spelling.** Probe both tenants and anon against public and seeded custom-schema tables before and after every repair. Try INSERT, UPDATE, DELETE as every client in rollback-only transactions. An affected row is an unauthorized write; an error is only accepted as a denial for SQLSTATE 42501. Unexpected failures fail closed. Privileged deterministic snapshots protect fixture rows and audit-only definitions/ACLs. Reject a catalog-only grader: RLS being enabled does not prove a safe policy. Reject scoring the presence of a preferred SQL statement: equivalent repairs must pass.
3. **Fresh databases per attempt; independent evidence.** Twelve seeded scenarios, three runs per control, isolated databases in one disposable cluster. Seeds change schema names, table names, UUIDs, and the broken-read cause. Both schemas always exist. Ten repair tasks plus two audit-only tasks. Each attempt gets fresh before/after probes; a faulty control cannot contaminate its twin. Export Supabase Evals `PROMPT.md`, `EVAL.ts`, and `remote/project.sql` using its real ToolScorer contract, not a new eval framework. Upstream hosted/platform-lite execution remains a separately documented integration boundary.

Write probes deliberately omit `RETURNING`: it adds a SELECT check, which can deny the probe even when a blind INSERT is allowed. Probe INSERT into each tenant, not only tenant A, and record the real command row count. The Python client uses cursor.rowcount; the exported SQL scorer uses GET DIAGNOSTICS in a rolled-back block. Counterexamples for anon-only INSERT and tenant-B-only INSERT failed before this correction and now reject in both graders.

## Interfaces and data flow

`Scenario(seed)` -> fixture SQL -> disposable database -> privileged baseline snapshot + unprivileged before probes -> `Candidate(scenario) -> SQL` -> owner connection -> after probes + snapshot -> hard-gated verdict -> JSON/HTML report.

Only the composition root discovers PostgreSQL binaries and paths. No connection URL is accepted: accidental production access is excluded. SQL identifiers are composed with psycopg Identifier; generated literal UUIDs are validated values. Candidate execution is bounded by database statement/lock timeouts. Infrastructure errors are not quality scores.

## Acceptance criteria and evidence contract

| ID | Acceptance criterion | Proof | Assertion |
|---|---|---|---|
| EC-1 | A safe read repair works for both tenants | Integration | Each sees exactly its two invoice IDs on both tables |
| EC-2 | A broad read policy restores reads but fails isolation | Integration + demo | Leaked row IDs are reported separately from success |
| EC-3 | All client writes remain denied | Integration | INSERT fails 42501; UPDATE/DELETE affect zero rows or fail 42501 |
| EC-4 | Repair does not destroy or rewrite seeded data | Integration | Canonical before/after data snapshots match |
| EC-5 | Audit-only controls leave data and definitions unchanged | Integration | Canonical baseline snapshot matches; mutation fails |
| EC-6 | Repeat runs do not share candidate state | Integration | 12 tasks × 3 independent databases per control |
| EC-7 | Upstream pack uses actual Evals shape | Integration | Generated scorer executes against a real PostgreSQL query bridge |

Unit tests cover scenario determinism, strict grading, aggregation and export. Database integration tests cover RLS, write attempts, rollback, snapshots, candidate errors, and isolation. No database mocks. The deterministic candidate replaces only agent reasoning. Not tested: hosted Supabase, real JWT verification, MCP tools, provider-backed agents, Docker CLI stack, malicious superuser sandbox escape. These are explicitly outside this local pack.

## Failure behavior and security

A successful empty read is not a repaired read. A read error is not proof of tenant isolation. Probe errors fail the attempt. Writes are rolled back even when permitted. Candidate SQL errors are recorded and fail the attempt; cluster failures abort the run. Only disposable fixture ownership is given to candidates, not cluster superuser or grader files. This is an eval harness for cooperative SQL repair experiments, not a hardened execution sandbox for adversarial SQL. Use containers/VMs before accepting arbitrary third-party submissions. Audit comparison is final-state comparison, not proof no transient mutation occurred.

## Rollout and migration

No deployed data or schema migration. The local demo creates and tears down its own PostgreSQL cluster. Exported Evals scenarios are reviewable files, not automatically installed into another checkout. Dependencies are pinned. CI installs PostgreSQL and runs the same tests/demo without API keys.

## At 100× scale

Bound database concurrency rather than spawning one server per attempt. Cache immutable fixture templates, clone a database per run, and retain failed-attempt artifacts with size limits. Run untrusted candidates in network-isolated containers with resource limits. Add held-out structural variants, independent real agents, and confidence estimates clustered by task, not inflated by deterministic repeats. Keep leak counts as a hard metric, never an averaged reward. Add PostgREST/Auth contract coverage separately; direct SQL RLS success is not proof of API configuration.

## Rejected scope

No generic agent framework, policy generator, hosted signup, production scanning, non-public inventory duplicate, frontend server, or paid LLM. A static local evidence viewer is sufficient. The repository was empty; the coding workflow defaults to its regular variant (no domain configuration exists).
