from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.modules.auth.models import AuthSession, ParentPin
from app.modules.auth.pin import hash_pin, verify_pin
from tests.conftest import PARENT_PIN


def test_pin_hash_round_trip():
    stored = hash_pin("1234")
    assert stored.startswith("scrypt$") and "1234" not in stored
    assert verify_pin("1234", stored) and not verify_pin("1235", stored)


def test_fresh_install_needs_setup(db_client):
    assert db_client.get("/api/auth/status").json() == {"setup_complete": False, "actor": None}
    assert db_client.post("/api/auth/parent", json={"pin": "1234"}).status_code == 409


def test_setup_signs_parent_in_and_runs_once(parent_client):
    status = parent_client.get("/api/auth/status").json()
    assert status["setup_complete"] and status["actor"]["role"] == "parent"
    assert parent_client.post("/api/auth/setup", json={"pin": "9999"}).status_code == 409


def test_pin_must_be_4_to_6_digits(db_client):
    for bad in ["123", "1234567", "12ab"]:
        assert db_client.post("/api/auth/setup", json={"pin": bad}).status_code == 422


def test_cookie_is_http_only(db_client):
    response = db_client.post("/api/auth/setup", json={"pin": PARENT_PIN})
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie


def test_parent_unlock_with_pin(parent_client):
    parent_client.post("/api/auth/logout")
    assert parent_client.get("/api/auth/status").json()["actor"] is None
    assert parent_client.post("/api/auth/parent", json={"pin": "0000"}).status_code == 401
    assert parent_client.post("/api/auth/parent", json={"pin": PARENT_PIN}).status_code == 204
    assert parent_client.get("/api/auth/status").json()["actor"]["role"] == "parent"


def test_lockout_after_five_wrong_pins(parent_client, db):
    parent_client.post("/api/auth/logout")
    codes = [parent_client.post("/api/auth/parent", json={"pin": "0000"}).status_code for _ in range(5)]
    assert codes == [401] * 5
    locked = parent_client.post("/api/auth/parent", json={"pin": PARENT_PIN})
    assert locked.status_code == 429 and int(locked.headers["retry-after"]) > 0
    db.execute(update(ParentPin).values(locked_until=datetime.now(UTC) - timedelta(seconds=1)))
    assert parent_client.post("/api/auth/parent", json={"pin": PARENT_PIN}).status_code == 204


def test_child_picks_profile_without_password(student_client, child):
    actor = student_client.get("/api/auth/status").json()["actor"]
    assert actor["role"] == "student" and actor["student_id"] == child["id"]


def test_picking_profile_is_logged(student_client, child):
    events = student_client.get("/api/events").json()
    assert [e["event_type"] for e in events] == ["profile.selected"]
    assert events[0]["student_id"] == child["id"]


def test_unknown_profile_cannot_sign_in(parent_client):
    response = parent_client.post(
        "/api/auth/student", json={"student_id": "00000000-0000-4000-8000-000000000000"}
    )
    assert response.status_code == 404


def test_logout_revokes_session(student_client):
    student_client.post("/api/auth/logout")
    assert student_client.get("/api/auth/status").json()["actor"] is None


def test_expired_session_is_rejected(student_client, db):
    db.execute(update(AuthSession).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    assert student_client.get("/api/auth/status").json()["actor"] is None


def test_parent_session_expires_sooner_than_student(parent_client, student_client, db):
    sessions = {s.role: s.expires_at - s.created_at for s in db.scalars(select(AuthSession))}
    assert sessions["parent"] < sessions["student"]


def test_tokens_are_stored_hashed(parent_client, db):
    cookie = parent_client.cookies.get("edaptive_session")
    assert cookie and db.scalars(select(AuthSession.token_hash)).all() != [cookie]
