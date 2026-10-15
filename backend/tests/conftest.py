import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db, get_engine
from app.main import create_app

PARENT_PIN = "2468"


def _db_available() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("select 1 from student_profile limit 1"))
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
    # Tests see an empty install even if a developer has real data in their local DB.
    session.execute(text("SET CONSTRAINTS ALL DEFERRED"))
    for table in ("auth_session", "parent_pin", "student_profile", "household"):
        session.execute(text(f"DELETE FROM {table}"))
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


def _new_client(db) -> TestClient:
    api = create_app()
    api.dependency_overrides[get_db] = lambda: db
    return TestClient(api)


@pytest.fixture
def parent_client(db):
    """First-run setup done; signed in as the parent."""
    client = _new_client(db)
    assert client.post("/api/auth/setup", json={"pin": PARENT_PIN}).status_code == 201
    return client


@pytest.fixture
def child(parent_client):
    return parent_client.post("/api/profiles", json={"display_name": "Zara", "grade": 3}).json()


@pytest.fixture
def student_client(db, child):
    """Separate browser, signed in as the child from the `child` fixture."""
    client = _new_client(db)
    assert client.post("/api/auth/student", json={"student_id": child["id"]}).status_code == 204
    return client
