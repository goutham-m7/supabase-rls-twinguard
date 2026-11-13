import pytest
from twinguard.fixture import seed_fixture, snapshot
from twinguard.scenario import scenarios


@pytest.mark.parametrize("task", scenarios(), ids=lambda s: s.id)
def test_fixture_exercises_broken_and_healthy_reads(cluster, task):
    with cluster.database() as name:
        seed_fixture(cluster, name, task)
        first = snapshot(cluster, name, task)
        assert first == snapshot(cluster, name, task)
        assert len(first["data"]) == 3
        assert all(len(rows) == 4 for rows in list(first["data"].values())[:2])
        with cluster.connect(name, "fixture_owner") as conn:
            assert conn.execute(
                "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user"
            ).fetchone() == (False,)


def test_snapshot_detects_policy_grants_and_data_changes(cluster):
    task = scenarios()[0]
    with cluster.database() as name:
        seed_fixture(cluster, name, task)
        before = snapshot(cluster, name, task)
        with cluster.connect(name, "fixture_owner") as conn:
            conn.execute("ALTER TABLE public.invoices_00 DISABLE ROW LEVEL SECURITY")
            conn.execute("UPDATE public.invoices_00 SET cents=1 WHERE id=1")
        after = snapshot(cluster, name, task)
        assert before["schema"] != after["schema"]
        assert before["data"] != after["data"]
