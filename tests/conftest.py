import pytest
from twinguard.postgres import Cluster


@pytest.fixture(scope="session")
def cluster():
    with Cluster() as instance:
        yield instance
