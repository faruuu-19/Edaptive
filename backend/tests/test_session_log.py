import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.contracts import ContractError, get_contracts
from app.session_log import append, read

EXAMPLES = get_contracts().root / "examples" / "events"


def example(name: str, **overrides) -> dict:
    event = json.loads((EXAMPLES / f"{name}.json").read_text())
    event["event_id"] = str(uuid.uuid4())
    event.update(overrides)
    return event


def test_append_then_read_in_order(db):
    session_id = str(uuid.uuid4())
    first = append(db, example("session.started", session_id=session_id))
    second = append(db, example("session.ended", session_id=session_id))
    assert second > first
    events = read(db, session_id=uuid.UUID(session_id))
    assert [e.event_type for e in events] == ["session.started", "session.ended"]
    assert events[0].to_contract()["payload"] == {"entry": "scheduled", "node_id": "math.g3.m5.l1"}


def test_append_is_idempotent(db):
    event = example("profile.selected")
    assert append(db, event) == append(db, event)


def test_invalid_event_is_never_stored(db):
    with pytest.raises(ContractError):
        append(db, example("session.ended", payload={"reason": "bored"}))


@pytest.mark.db
@pytest.mark.parametrize(
    "statement", ["UPDATE event SET source = 'x'", "DELETE FROM event", "TRUNCATE event"]
)
def test_log_is_append_only(db, statement):
    append(db, example("profile.selected"))
    db.flush()
    with pytest.raises(DBAPIError, match="append-only"):
        with db.begin_nested():
            db.execute(text(statement))


def test_http_round_trip(db_client):
    session_id = str(uuid.uuid4())
    response = db_client.post("/api/events", json=example("session.started", session_id=session_id))
    assert response.status_code == 201
    listed = db_client.get("/api/events", params={"session_id": session_id}).json()
    assert [e["event_type"] for e in listed] == ["session.started"]


def test_http_rejects_unregistered_type(db_client):
    response = db_client.post("/api/events", json=example("session.started", event_type="session.paused"))
    assert response.status_code == 422
    assert "not registered" in response.json()["detail"][0]
