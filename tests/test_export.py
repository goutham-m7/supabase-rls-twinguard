import json
from pathlib import Path
import subprocess
import pytest
import psycopg
from twinguard.controls import CONTROLS
from twinguard.export import export_pack
from twinguard.fixture import seed_fixture
from twinguard.scenario import scenarios

@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    destination = tmp_path_factory.mktemp("evals-pack")
    export_pack(destination)
    return destination


@pytest.mark.parametrize("control", ["safe", "unsafe", "no-tools", "blind-insert", "second-tenant"])
@pytest.mark.parametrize("seed", range(12))
def test_actual_exported_typescript_scorer_against_postgres(cluster, exported, seed, control):
    task = scenarios()[seed]
    scenario = exported / "regression" / task.id
    assert (scenario / "PROMPT.md").read_text().startswith("---\nstage:")
    assert (scenario / "remote" / "project.sql").is_file()
    bridge = Path(__file__).parent / "upstream_bridge.mjs"
    with cluster.database() as name:
        seed_fixture(cluster, name, task)
        with cluster.connect(name, "fixture_owner") as owner:
            migration = CONTROLS[control if control in CONTROLS else "safe"](task)
            if control == "blind-insert":
                migration += f"CREATE POLICY blind ON public.{task.table} FOR INSERT TO anon WITH CHECK (true);"
            if control == "second-tenant":
                migration += f"CREATE POLICY second_tenant ON public.{task.table} FOR INSERT TO authenticated WITH CHECK (tenant_id='{task.tenants[1]}');"
            if migration:
                owner.execute(migration)
        process = subprocess.Popen(["node", str(bridge), str(scenario / "EVAL.ts")],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True)
        with cluster.connect(name) as conn:
            conn.autocommit = True
            for line in process.stdout:
                message = json.loads(line)
                if "result" in message:
                    result = message["result"]
                    break
                try:
                    cursor = conn.execute(message["sql"])
                    rows = []
                    while True:
                        if cursor.description:
                            columns = [c.name for c in cursor.description]
                            rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
                        if not cursor.nextset():
                            break
                    reply = {"rows": rows}
                except psycopg.Error as exc:
                    reply = {"error": str(exc), "code": exc.sqlstate}
                process.stdin.write(json.dumps(reply) + "\n")
                process.stdin.flush()
        _, stderr = process.communicate(timeout=15)
        assert process.returncode == 0, stderr
        assert result["passed"] == (control == "safe" or control == "no-tools" and task.audit_only), result
        assert len(result["checks"]) == 5
