from pathlib import Path
import psycopg
import pytest
from twinguard.postgres import Cluster


def test_cluster_is_private_and_cleaned_up():
    with Cluster() as cluster:
        directory = Path(cluster.directory)
        with cluster.connect() as conn:
            assert conn.execute("SHOW listen_addresses").fetchone()[0] == ""
        with cluster.database() as name:
            with cluster.connect(name, "authenticated") as conn:
                assert conn.execute("SELECT current_user").fetchone()[0] == "authenticated"
                assert not conn.execute(
                    "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user"
                ).fetchone()[0]
        with pytest.raises(psycopg.OperationalError):
            cluster.connect(name)
    assert not directory.exists()


def test_database_is_removed_after_exception():
    with Cluster() as cluster:
        with pytest.raises(RuntimeError, match="candidate"):
            with cluster.database() as name:
                raise RuntimeError("candidate")
        with cluster.connect() as conn:
            assert conn.execute(
                "SELECT count(*) FROM pg_database WHERE datname=%s", (name,)
            ).fetchone() == (0,)
