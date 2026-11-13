import pytest
from twinguard.fixture import seed_fixture, snapshot
from twinguard.probe import probe
from twinguard.scenario import scenarios


@pytest.mark.parametrize("task", scenarios(), ids=lambda s: s.id)
def test_real_client_before_matrix_and_write_rollback(cluster, task):
    with cluster.database() as name:
        seed_fixture(cluster, name, task)
        before = snapshot(cluster, name, task)
        evidence = probe(cluster, name, task)
        assert len(evidence) == 24  # 2 tables × 3 identities × 4 operations
        reads = [p for p in evidence if p["operation"] == "select"]
        for p in reads:
            broken = p["schema"] == task.target_schema and not task.audit_only
            expected = [] if p["actor"] == "anon" or broken else task.expected_ids(int(p["actor"]))
            assert p["ids"] == expected
            assert p["sqlstate"] == ("42501" if broken and task.fault == "missing_grant" else None)
        assert all(not p["ids"] for p in evidence if p["operation"] != "select")
        assert before == snapshot(cluster, name, task)


def test_permitted_writes_are_observed_but_never_committed(cluster):
    task = scenarios()[0]
    with cluster.database() as name:
        seed_fixture(cluster, name, task)
        with cluster.connect(name, "fixture_owner") as conn:
            conn.execute("CREATE POLICY wide ON public.invoices_00 FOR ALL TO PUBLIC USING (true) WITH CHECK (true)")
        before = snapshot(cluster, name, task)
        evidence = probe(cluster, name, task)
        assert all(p["ids"] for p in evidence if p["schema"] == "public")
        assert before == snapshot(cluster, name, task)
