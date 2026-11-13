import json
from pathlib import Path
import subprocess
import pytest
import psycopg
from twinguard.controls import CONTROLS
from twinguard.export import export_pack
from twinguard.fixture import seed_fixture
from twinguard.scenario import scenarios


@pytest.mark.parametrize("control", ["safe", "unsafe", "no-tools"])
@pytest.mark.parametrize("seed", [0, 1, 2, 10, 11])
def test_actual_exported_typescript_scorer_against_postgres(cluster, tmp_path, seed, control):
    task = scenarios()[seed]
    export_pack(tmp_path)
    scenario = tmp_path / "regression" / task.id
    assert (scenario / "PROMPT.md").read_text().startswith("---\nstage:")
    assert (scenario / "remote" / "project.sql").is_file()
    bridge = Path(__file__).parent / "upstream_bridge.mjs"
    with cluster.database() as name:
        seed_fixture(cluster, name, task)
        with cluster.connect(name, "fixture_owner") as owner:
            migration = CONTROLS[control](task)
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
