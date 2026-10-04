import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db, get_engine
from app.main import create_app


def _db_available() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("select 1 from event limit 1"))
        return True
    except Exception:
        return False


@pytest.fixture
def db():
    """A session inside a transaction that is always rolled back, so tests leave no rows
    behind (the event table refuses DELETE/TRUNCATE by design)."""
    if not _db_available():
        if os.environ.get("REQUIRE_DB"):
            pytest.fail("REQUIRE_DB is set but the database is unreachable or not migrated")
        pytest.skip("database not available; run `make db-up migrate`")
    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def db_client(db):
    api = create_app()
    api.dependency_overrides[get_db] = lambda: db
    return TestClient(api)
