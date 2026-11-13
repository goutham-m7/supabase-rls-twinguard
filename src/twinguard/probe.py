"""Run real SQL clients. Never use owner/service-role reads as access evidence."""
import json
import psycopg
from .fixture import table_name
from .scenario import Scenario


def probe(cluster, database: str, task: Scenario) -> list[dict]:
    evidence = []
    for schema, table in task.tables:
        qualified = table_name(schema, table)
        for actor in ("0", "1", "anon"):
            role = "anon" if actor == "anon" else "authenticated"
            claims = {"role": role}
            if actor != "anon":
                claims["sub"] = task.users[int(actor)]
            operations = {
                "select": f"SELECT id FROM {qualified} ORDER BY id",
                "insert": f"INSERT INTO {qualified} VALUES (999, '{task.tenants[0]}', 777) RETURNING id",
                "update": f"UPDATE {qualified} SET cents=cents+1 RETURNING id",
                "delete": f"DELETE FROM {qualified} RETURNING id",
            }
            for operation, statement in operations.items():
                ids, state = [], None
                # One fresh connection/transaction per probe: failures and writes cannot poison another.
                with cluster.connect(database, role) as conn:
                    try:
                        conn.execute("SELECT set_config('request.jwt.claims', %s, true)", (json.dumps(claims),))
                        ids = sorted(row[0] for row in conn.execute(statement).fetchall())
                    except psycopg.Error as exc:
                        state = exc.sqlstate
                    finally:
                        conn.rollback()
                evidence.append({"schema": schema, "table": table, "actor": actor,
                                 "operation": operation, "ids": ids, "sqlstate": state})
    return evidence
