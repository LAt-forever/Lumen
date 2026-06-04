from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from service.db import configure_database, init_db


@pytest.fixture()
def client(tmp_path: Path):
    configure_database(f"sqlite:///{tmp_path / 'test.db'}")
    init_db()
    from service.main import app

    with TestClient(app) as test_client:
        yield test_client
