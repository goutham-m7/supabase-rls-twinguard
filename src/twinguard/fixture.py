"""Synthetic invoices and snapshots independently read by the grader."""
import subprocess
from psycopg import sql
from .scenario import Scenario


def table_name(schema: str, table: str) -> str:
    return sql.Identifier(schema, table).as_string()


def safe_expression() -> str:
    return "tenant_id IN (SELECT tenant_id FROM public.memberships WHERE user_id = (SELECT auth.uid()))"


def fixture_sql(task: Scenario) -> str:
    statements = [f"CREATE SCHEMA {sql.Identifier(task.custom_schema).as_string()};",
                  "CREATE TABLE public.memberships (user_id uuid PRIMARY KEY, tenant_id uuid NOT NULL);",
                  "ALTER TABLE public.memberships ENABLE ROW LEVEL SECURITY;",
                  "CREATE POLICY member_self ON public.memberships FOR SELECT TO authenticated USING (user_id=(SELECT auth.uid()));",
                  "GRANT SELECT ON public.memberships TO authenticated;"]
    for user, tenant in zip(task.users, task.tenants, strict=True):
        statements.append(f"INSERT INTO public.memberships VALUES ('{user}', '{tenant}');")
    for schema, table in task.tables:
        qualified = table_name(schema, table)
        statements.extend([
            f"GRANT USAGE ON SCHEMA {sql.Identifier(schema).as_string()} TO authenticated, anon;",
            f"CREATE TABLE {qualified} (id integer PRIMARY KEY, tenant_id uuid NOT NULL, cents integer NOT NULL CHECK (cents > 0));",
            f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY;",
            # Writes are granted to ensure denied writes exercise RLS, not just missing grants.
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {qualified} TO authenticated, anon;",
        ])
        for actor, tenant in enumerate(task.tenants):
            for row_id in task.expected_ids(actor):
                statements.append(f"INSERT INTO {qualified} VALUES ({row_id}, '{tenant}', {1000 + row_id});")
        broken = schema == task.target_schema and not task.audit_only
        expression = safe_expression()
        if broken and task.fault == "false":
            expression = "false"
        elif broken and task.fault == "wrong_identity":
            expression = "tenant_id = (SELECT auth.uid())"
        statements.append(f"CREATE POLICY tenant_read ON {qualified} FOR SELECT TO authenticated USING ({expression});")
        if broken and task.fault == "missing_grant":
            statements.append(f"REVOKE SELECT ON {qualified} FROM authenticated, anon;")
    return "\n".join(statements) + "\n"


def seed_fixture(cluster, database: str, task: Scenario):
    with cluster.connect(database, "fixture_owner") as conn:
        conn.execute(fixture_sql(task))


def snapshot(cluster, database: str, task: Scenario) -> dict:
    data = {}
    with cluster.connect(database) as conn:
        for schema, table in (*task.tables, ("public", "memberships")):
            qualified = table_name(schema, table)
            rows = conn.execute(f"SELECT row_to_json(t) FROM (SELECT * FROM {qualified} ORDER BY 1) t").fetchall()
            data[f"{schema}.{table}"] = [row[0] for row in rows]
    dump = subprocess.run(
        [str(cluster.bin / "pg_dump"), "--host", cluster.directory, "--port", "55439", "--username", "postgres",
         "--dbname", database, "--schema-only", "--no-owner"],
        capture_output=True, text=True, timeout=15, check=True,
    ).stdout
    # PostgreSQL security releases put a random psql restriction nonce in dumps.
    schema = "\n".join(line for line in dump.splitlines() if not line.startswith(("\\restrict ", "\\unrestrict ")))
    return {"data": data, "schema": schema}
