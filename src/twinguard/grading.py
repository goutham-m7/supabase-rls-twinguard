"""Conjunctive gates: a leak never trades off against a repaired happy path."""

from .scenario import Scenario


def grade(
    task: Scenario, evidence: list[dict], before: dict, after: dict, error: str | None
) -> dict:
    expected_keys = {
        (s, t, a, op)
        for s, t in task.tables
        for a in ("0", "1", "anon")
        for op in ("select", "insert", "insert_other", "update", "delete")
    }
    keys = [(p["schema"], p["table"], p["actor"], p["operation"]) for p in evidence]
    matrix_complete = len(keys) == len(expected_keys) and set(keys) == expected_keys
    repaired, reads, writes, valid, leaks = True, 0, 0, True, []
    for p in evidence:
        state = p["sqlstate"]
        valid &= state in (None, "42501")
        if p["operation"] == "select":
            expected = [] if p["actor"] == "anon" else task.expected_ids(int(p["actor"]))
            if p["actor"] != "anon":
                repaired &= state is None and set(expected).issubset(p["ids"])
            foreign = [row_id for row_id in p["ids"] if row_id not in expected]
            reads += len(foreign)
            if foreign:
                leaks.append({**p, "ids": foreign})
        else:
            writes += p["affected"]
    checks = {
        "matrix_complete": matrix_complete,
        "read_repaired": bool(repaired),
        "tenant_isolation": reads == 0,
        "writes_denied": writes == 0,
        "probe_errors_absent": bool(valid),
        "data_preserved": before["data"] == after["data"],
        "audit_unchanged": not task.audit_only or before == after,
        "candidate_completed": error is None,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "unauthorized_reads": reads,
        "unauthorized_writes": writes,
        "leaks": leaks,
    }
