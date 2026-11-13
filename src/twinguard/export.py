"""Export actual PROMPT/EVAL/remote files, not an alternative eval schema."""
from importlib.resources import files
import json
from pathlib import Path
from .fixture import fixture_sql, seed_fixture, table_name
from .postgres import Cluster
from .scenario import scenarios

UPSTREAM = "5d79ba5da00260e98241fb6f6da66b7df87fe383"


def data_sql(task) -> str:
    pieces = []
    for schema, table in (*task.tables, ("public", "memberships")):
        name = table_name(schema, table)
        pieces.append(f"'{schema}.{table}', (SELECT jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text) FROM {name} t)")
    return "SELECT jsonb_build_object(" + ",".join(pieces) + ") AS data"


def state_sql(task) -> str:
    schemas = f"('public', '{task.custom_schema}')"
    # Normalize away owner/grantor identities: upstream seeds as its own DB owner.
    return f"""SELECT jsonb_build_object(
      'data', ({data_sql(task)}),
      'relations', (SELECT jsonb_agg(to_jsonb(t) ORDER BY t.schema, t.name) FROM (
        SELECT n.nspname AS schema, c.relname AS name, c.relkind, c.relrowsecurity, c.relforcerowsecurity
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN {schemas}) t),
      'columns', (SELECT jsonb_agg(to_jsonb(t) ORDER BY t.table_schema, t.table_name, t.ordinal_position)
        FROM (SELECT table_schema, table_name, column_name, ordinal_position, column_default,
          is_nullable, data_type, udt_schema, udt_name FROM information_schema.columns
          WHERE table_schema IN {schemas}) t),
      'policies', (SELECT jsonb_agg(to_jsonb(t) ORDER BY t.schemaname, t.tablename, t.policyname)
        FROM pg_policies t WHERE t.schemaname IN {schemas}),
      'grants', (SELECT jsonb_agg(to_jsonb(t) ORDER BY t.table_schema, t.table_name, t.grantee, t.privilege_type) FROM (
        SELECT table_schema, table_name, grantee, privilege_type, is_grantable
        FROM information_schema.table_privileges WHERE table_schema IN {schemas}
        AND grantee IN ('anon', 'authenticated', 'PUBLIC')) t),
      'functions', (SELECT jsonb_agg(pg_get_functiondef(p.oid) ORDER BY p.proname)
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname IN {schemas})
    ) AS state"""


def export_pack(destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    template = files("twinguard").joinpath("evals_scorer.ts").read_text()
    with Cluster() as cluster:
        for task in scenarios():
            path = destination / "regression" / task.id
            if path.exists():
                raise FileExistsError(f"Refusing to overwrite {path}")
            (path / "remote").mkdir(parents=True)
            with cluster.database() as name:
                seed_fixture(cluster, name, task)
                with cluster.connect(name) as conn:
                    state = conn.execute(state_sql(task)).fetchone()[0]
                    data = conn.execute(data_sql(task)).fetchone()[0]
            spec = {"tables": task.tables, "users": task.users, "tenants": task.tenants,
                    "auditOnly": task.audit_only, "stateSql": state_sql(task), "dataSql": data_sql(task),
                    "state": state, "data": data}
            prompt = ("---\nstage: " + ("investigate" if task.audit_only else "resolve") +
                      "\ninterface: mcp\nproduct: [database, auth]\ntopic: [rls, security]\n"
                      "motivation: https://supabase.com/docs/guides/database/postgres/row-level-security\n---\n\n" + task.prompt + "\n")
            (path / "PROMPT.md").write_text(prompt)
            (path / "remote" / "project.sql").write_text(fixture_sql(task))
            (path / "EVAL.ts").write_text(template.replace("__SPEC__", json.dumps(spec, sort_keys=True)))
    (destination / "upstream.json").write_text(json.dumps({"repository": "https://github.com/supabase/evals", "commit": UPSTREAM,
        "contract": "ToolScorer / ctx.query; SQL clients, not PostgREST", "cases": 12}, indent=2) + "\n")
