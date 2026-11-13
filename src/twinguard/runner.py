"""An agentprobe-style callable adapter with independent before/after evidence."""
from collections.abc import Callable
import hashlib
import json
import psycopg
from .fixture import seed_fixture, snapshot
from .grading import grade
from .probe import probe
from .scenario import Scenario

Candidate = Callable[[Scenario], str]


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def run_attempt(cluster, task: Scenario, candidate: Candidate, label: str, run: int) -> dict:
    with cluster.database() as name:
        seed_fixture(cluster, name, task)
        before_state = snapshot(cluster, name, task)
        before = probe(cluster, name, task)
        migration = candidate(task)
        error = None
        if migration.strip():
            try:
                with cluster.connect(name, "fixture_owner") as conn:
                    conn.execute(migration)
            except psycopg.Error as exc:
                error = exc.sqlstate or type(exc).__name__
        after = probe(cluster, name, task)
        try:
            after_state = snapshot(cluster, name, task)
        except psycopg.Error:
            after_state = {"data": None, "schema": None}
        verdict = grade(task, after, before_state, after_state, error)
        for leak in verdict["leaks"]:
            rows = before_state["data"][f"{leak['schema']}.{leak['table']}"]
            leak["rows"] = [row for row in rows if row["id"] in leak["ids"]]
        return {"task": task.id, "seed": task.seed, "audit_only": task.audit_only,
                "control": label, "run": run, "candidate_sql": migration, "candidate_error": error,
                "before": before, "after": after, "state_before": digest(before_state),
                "state_after": digest(after_state), **verdict}
