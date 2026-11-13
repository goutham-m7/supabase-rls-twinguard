from twinguard.scenario import scenarios


def test_seeded_tasks_are_reproducible_and_distinct():
    tasks = scenarios()
    assert tasks == scenarios()
    assert len(tasks) == 12
    assert len({s.users for s in tasks}) == 12
    assert len({s.custom_schema for s in tasks}) == 12
    assert {s.fault for s in tasks} == {"false", "wrong_identity", "missing_grant"}
    assert sum(s.audit_only for s in tasks) == 2
    assert sum(s.target_schema == "public" for s in tasks) == 6
    for task in tasks:
        assert task.users[0] != task.users[1]
        assert task.tenants[0] != task.tenants[1]
        assert task.users != task.tenants
        assert len(task.tables) == 2
