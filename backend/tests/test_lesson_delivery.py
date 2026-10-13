import copy
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.modules.lesson_delivery import router, runtime
from app.modules.lesson_delivery.models import Timetable
from app.session_log.models import Event

CID = "math_g3_m7_l5_compare_classify_other_polygons"
TIMING = {"minutes": 15, "basis": "card_plan", "buffer_seconds": 180, "estimated": True}


@pytest.fixture(autouse=True)
def local_service(monkeypatch):
    monkeypatch.setattr(
        router,
        "available",
        lambda: [
            {
                "id": CID,
                "grade": 3,
                "module": 7,
                "title": "Polygons",
                "card_version": 2,
                "ready_for_delivery": False,
                "estimated_minutes": 15,
                "timing": TIMING,
            },
            {
                "id": "math_g2_m1_l1_pairs_to_ten",
                "grade": 2,
                "module": 1,
                "title": "Pairs",
                "card_version": 2,
                "ready_for_delivery": False,
                "estimated_minutes": 15,
                "timing": TIMING,
            },
        ],
    )
    monkeypatch.setattr(runtime, "voice_request", lambda *args: {"reserved": True})


def plan(child, **changes):
    return {
        "student_id": child["id"],
        "starts_at": (datetime.now(UTC) + timedelta(minutes=20)).isoformat(),
        "allow_drafts": True,
        **changes,
    }


def prepared(db, response):
    row = db.get(Timetable, uuid.UUID(response["id"]))
    state = copy.deepcopy(row.state)
    slot = state["slots"][0]
    slot.update(
        preparation={"status": "ready", "percent": 100}, segment_count=3, narrated_positions=[0, 1, 2]
    )
    row.state = state
    db.flush()
    return row, slot


def action(client, timetable, slot, kind, **values):
    return client.post(
        "/api/lesson_delivery/" + timetable["id"] + "/action",
        json={"slot_id": slot["id"], "action": kind, **values},
    )


def test_parent_creates_durable_grade_matched_plan(parent_client, child, db):
    response = parent_client.post("/api/lesson_delivery", json=plan(child))
    assert response.status_code == 201
    saved = response.json()
    assert saved["slots"][0]["concept_id"] == CID
    assert db.get(Timetable, uuid.UUID(saved["id"])).state["slots"][0]["timing"]["buffer_seconds"] == 180
    assert (
        parent_client.get("/api/lesson_delivery/student/" + child["id"]).json()["timetables"][0]["id"]
        == saved["id"]
    )


def test_student_cannot_plan_or_access_another_child(student_client, child):
    assert student_client.post("/api/lesson_delivery", json=plan(child)).status_code == 403
    assert student_client.get("/api/lesson_delivery/student/" + str(uuid.uuid4())).status_code == 403


def test_drafts_and_other_grade_and_naive_times_rejected(parent_client, child):
    assert parent_client.post("/api/lesson_delivery", json=plan(child, allow_drafts=False)).status_code == 422
    assert (
        parent_client.post(
            "/api/lesson_delivery", json=plan(child, concept_ids=["math_g2_m1_l1_pairs_to_ten"])
        ).status_code
        == 422
    )
    assert (
        parent_client.post(
            "/api/lesson_delivery", json=plan(child, starts_at="2026-10-15T12:00:00")
        ).status_code
        == 422
    )


def test_due_time_and_ready_checks_are_server_enforced(parent_client, child, db, monkeypatch):
    result = parent_client.post("/api/lesson_delivery", json=plan(child)).json()
    row, slot = prepared(db, result)
    assert action(parent_client, result, slot, "start").status_code == 409
    monkeypatch.setattr(runtime.time, "time", lambda: slot["start_ms"] / 1000 + 1)
    state = copy.deepcopy(row.state)
    state["slots"][0]["preparation"]["status"] = "preparing"
    row.state = state
    assert action(parent_client, result, slot, "start").status_code == 409


def test_start_position_reload_finish_events_are_real(parent_client, child, db, monkeypatch):
    result = parent_client.post("/api/lesson_delivery", json=plan(child)).json()
    _, slot = prepared(db, result)
    monkeypatch.setattr(runtime.time, "time", lambda: slot["start_ms"] / 1000 + 1)
    assert action(parent_client, result, slot, "start").status_code == 200
    assert action(parent_client, result, slot, "position", position=2).status_code == 409
    assert action(parent_client, result, slot, "finish").status_code == 409
    assert action(parent_client, result, slot, "position", position=1).status_code == 200
    assert (
        parent_client.get("/api/lesson_delivery/student/" + child["id"]).json()["timetables"][0]["slots"][0][
            "position"
        ]
        == 1
    )
    assert action(parent_client, result, slot, "position", position=2).status_code == 200
    assert action(parent_client, result, slot, "finish").json()["status"] == "completed"
    events = list(db.scalars(select(Event).where(Event.student_id == uuid.UUID(child["id"]))))
    types = [e.event_type for e in events]
    assert types.count("session.started") == 1 and types.count("session.ended") == 1
    assert types.count("lesson.delivery_changed") == 4
    assert action(parent_client, result, slot, "start").status_code == 409


def test_starting_a_class_waits_long_enough_for_a_released_voice_to_reload(
    parent_client, child, db, monkeypatch
):
    """After a class ends or is unattended the voice model is unloaded, so the next
    Start may have to load it again; a five second request timeout would fail that start."""
    calls = []
    monkeypatch.setattr(runtime, "voice_request", lambda *args: calls.append(args) or {"reserved": True})
    result = parent_client.post("/api/lesson_delivery", json=plan(child)).json()
    _, slot = prepared(db, result)
    monkeypatch.setattr(runtime.time, "time", lambda: slot["start_ms"] / 1000 + 1)
    assert action(parent_client, result, slot, "start").status_code == 200
    reserve = [c for c in calls if c[0].endswith("/reserve")]
    assert reserve, "start must reserve the teacher voice"
    assert reserve[0][2] >= 30


def test_borrow_and_cancellation_block_lesson_access(parent_client, child, db, monkeypatch):
    result = parent_client.post("/api/lesson_delivery", json=plan(child)).json()
    _, slot = prepared(db, result)
    monkeypatch.setattr(runtime.time, "time", lambda: slot["start_ms"] / 1000 + 1)
    delayed = action(parent_client, result, slot, "borrow").json()
    assert delayed["slots"][0]["start_ms"] == slot["start_ms"] + 300000
    assert delayed["slots"][0]["preparation"]["status"] == "ready"
    assert action(parent_client, result, slot, "cancel").json()["status"] == "cancelled"
    assert (
        parent_client.get("/api/lesson_delivery/" + result["id"] + "/lesson/" + slot["id"]).status_code == 409
    )


def test_only_one_active_timetable_per_child(parent_client, child):
    assert parent_client.post("/api/lesson_delivery", json=plan(child)).status_code == 201
    assert parent_client.post("/api/lesson_delivery", json=plan(child)).status_code == 409


def test_position_and_finish_require_narration_not_just_api_navigation(parent_client, child, db, monkeypatch):
    result = parent_client.post("/api/lesson_delivery", json=plan(child)).json()
    row, slot = prepared(db, result)
    state = copy.deepcopy(row.state)
    state["slots"][0]["narrated_positions"] = []
    row.state = state
    monkeypatch.setattr(runtime.time, "time", lambda: slot["start_ms"] / 1000 + 1)
    assert action(parent_client, result, slot, "start").status_code == 200
    assert action(parent_client, result, slot, "position", position=1).status_code == 409


def test_borrow_moves_future_lessons_and_keeps_break_duration(parent_client, child, db, monkeypatch):
    second = "math_g3_m7_l6_sort_quadrilaterals"
    cards = router.available()
    monkeypatch.setattr(router, "available", lambda: cards + [{**cards[0], "id": second}])
    result = parent_client.post("/api/lesson_delivery", json=plan(child, concept_ids=[CID, second])).json()
    _, slot = prepared(db, result)
    monkeypatch.setattr(runtime.time, "time", lambda: slot["start_ms"] / 1000 + 1)
    delayed = action(parent_client, result, slot, "borrow").json()
    for before, after in zip(result["slots"], delayed["slots"], strict=True):
        assert after["start_ms"] - before["start_ms"] == 300000
        assert after["end_ms"] - before["end_ms"] == 300000
    assert delayed["slots"][1]["end_ms"] - delayed["slots"][1]["start_ms"] == 300000
