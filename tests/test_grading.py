from copy import deepcopy
import pytest
from twinguard.grading import grade
from twinguard.scenario import scenarios


def clean(task):
    return [dict(schema=s, table=t, actor=a, operation=op,
                 ids=task.expected_ids(int(a)) if op == "select" and a != "anon" else [],
                 sqlstate=None, affected=0)
            for s,t in task.tables for a in ("0", "1", "anon")
            for op in ("select", "insert", "insert_other", "update", "delete")]


def test_behavior_not_policy_text_decides_pass():
    task = scenarios()[0]
    result = grade(task, clean(task), {"data": [], "schema": "old"}, {"data": [], "schema": "equivalent"}, None)
    assert result["passed"]


@pytest.mark.parametrize("mutation", ["leak", "write", "error", "missing", "duplicate", "empty", "data", "candidate"])
def test_each_hard_failure_rejects_independently(mutation):
    task = scenarios()[0]
    evidence = clean(task)
    before = {"data": [], "schema": "old"}
    after = deepcopy(before)
    error = None
    if mutation == "leak":
        evidence[0]["ids"] += [3]
    elif mutation == "write":
        evidence[1]["affected"] = 1
    elif mutation == "error":
        evidence[1]["sqlstate"] = "42P01"
    elif mutation == "missing":
        evidence.pop()
    elif mutation == "duplicate":
        evidence[-1] = evidence[0]
    elif mutation == "empty":
        evidence[0]["ids"] = []
    elif mutation == "data":
        after["data"] = ["changed"]
    else:
        error = "42601"
    result = grade(task, evidence, before, after, error)
    assert not result["passed"]
    if mutation == "leak":
        assert result["unauthorized_reads"] == 1
    if mutation == "write":
        assert result["unauthorized_writes"] == 1


def test_audit_rejects_schema_changes_even_with_perfect_access():
    task = scenarios()[10]
    result = grade(task, clean(task), {"data": [], "schema": "a"}, {"data": [], "schema": "b"}, None)
    assert not result["passed"]
    assert not result["checks"]["audit_unchanged"]
