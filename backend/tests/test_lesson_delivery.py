import copy
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.modules.lesson_delivery import curriculum, router, routines, runtime
from app.modules.lesson_delivery.models import LearningProgress, SchoolRoutine, Timetable
from app.session_log.models import Event

CID = "math_g3_m1_l1_compare_classify_other_polygons"
TIMING = {"minutes": 15, "basis": "card_plan", "buffer_seconds": 180, "estimated": True}


@pytest.fixture(autouse=True)
def local_service(monkeypatch):
    monkeypatch.setenv("EDAPTIVE_ALLOW_DRAFT_LESSONS", "1")
    monkeypatch.setattr(
        curriculum,
        "module_index",
        lambda grade, paired: [
            {
                "module": 1,
                "expected": 2,
                "lessons": {
                    int(card["id"].split("_")[3][1:]): card["id"] for card in paired if card["grade"] == grade
                },
            }
        ],
    )
    monkeypatch.setattr(routines, "clock_now", lambda: datetime(2026, 10, 14, 3, 0, tzinfo=UTC))
    monkeypatch.setattr(
        router,
        "available",
        lambda: [
            {
                "id": CID,
                "grade": 3,
                "module": 1,
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


def save_time(client, child, **changes):
    return client.put("/api/lesson_delivery/routine/" + child["id"], json={"start_time": "09:00", **changes})


def create_plan(client, child):
    response = save_time(client, child)
    assert response.status_code == 200
    return response.json()["timetable"]


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
    saved = create_plan(parent_client, child)
    assert saved["slots"][0]["concept_id"] == CID
    assert db.get(Timetable, uuid.UUID(saved["id"])).state["slots"][0]["timing"]["buffer_seconds"] == 180
    assert (
        parent_client.get("/api/lesson_delivery/student/" + child["id"]).json()["timetables"][0]["id"]
        == saved["id"]
    )


def test_student_cannot_plan_or_access_another_child(student_client, child):
    assert save_time(student_client, child).status_code == 403
    assert student_client.get("/api/lesson_delivery/student/" + str(uuid.uuid4())).status_code == 403


@pytest.mark.parametrize(
    "field,value",
    [
        ("concept_ids", [CID]),
        ("break_minutes", 60),
        ("prepare_minutes", 1),
        ("starts_at", "2026-10-15T09:00:00+05:00"),
        ("allow_drafts", True),
    ],
)
def test_parent_cannot_override_system_choices(parent_client, child, field, value):
    assert save_time(parent_client, child, **{field: value}).status_code == 422
    assert parent_client.post("/api/lesson_delivery", json={"student_id": child["id"]}).status_code in {
        404,
        405,
    }


@pytest.mark.parametrize("value", ["24:00", "09:60", "9:00", "09:00:01", "2026-10-15T09:00", ""])
def test_invalid_daily_time_rejected(parent_client, child, value):
    assert save_time(parent_client, child, start_time=value).status_code == 422


def test_due_time_and_ready_checks_are_server_enforced(parent_client, student_client, child, db, monkeypatch):
    result = create_plan(parent_client, child)
    row, slot = prepared(db, result)
    monkeypatch.setattr(runtime.time, "time", lambda: slot["start_ms"] / 1000 - 1)
    assert action(student_client, result, slot, "start").status_code == 409
    monkeypatch.setattr(runtime.time, "time", lambda: slot["start_ms"] / 1000 + 1)
    state = copy.deepcopy(row.state)
    state["slots"][0]["preparation"]["status"] = "preparing"
    row.state = state
    assert action(student_client, result, slot, "start").status_code == 409


def test_start_position_reload_finish_events_are_real(parent_client, student_client, child, db, monkeypatch):
    result = create_plan(parent_client, child)
    _, slot = prepared(db, result)
    monkeypatch.setattr(runtime.time, "time", lambda: slot["start_ms"] / 1000 + 1)
    assert action(student_client, result, slot, "start").status_code == 200
    assert db.get(LearningProgress, uuid.UUID(child["id"])).state["modules"][0]["status"] == "in_progress"
    assert action(student_client, result, slot, "position", position=2).status_code == 409
    assert action(student_client, result, slot, "finish").status_code == 409
    assert action(student_client, result, slot, "position", position=1).status_code == 200
    assert (
        parent_client.get("/api/lesson_delivery/student/" + child["id"]).json()["timetables"][0]["slots"][0][
            "position"
        ]
        == 1
    )
    assert action(student_client, result, slot, "position", position=2).status_code == 200
    assert action(student_client, result, slot, "finish").json()["status"] == "completed"
    assert db.get(LearningProgress, uuid.UUID(child["id"])).state["modules"][0]["delivered_lessons"] == 1
    events = list(db.scalars(select(Event).where(Event.student_id == uuid.UUID(child["id"]))))
    types = [e.event_type for e in events]
    assert types.count("session.started") == 1 and types.count("session.ended") == 1
    assert types.count("lesson.delivery_changed") == 4
    assert action(student_client, result, slot, "start").status_code == 409


def test_starting_a_class_waits_long_enough_for_a_released_voice_to_reload(
    parent_client, student_client, child, db, monkeypatch
):
    """After a class ends or is unattended the voice model is unloaded, so the next
    Start may have to load it again; a five second request timeout would fail that start."""
    calls = []
    monkeypatch.setattr(runtime, "voice_request", lambda *args: calls.append(args) or {"reserved": True})
    result = create_plan(parent_client, child)
    _, slot = prepared(db, result)
    monkeypatch.setattr(runtime.time, "time", lambda: slot["start_ms"] / 1000 + 1)
    assert action(student_client, result, slot, "start").status_code == 200
    reserve = [c for c in calls if c[0].endswith("/reserve")]
    assert reserve, "start must reserve the teacher voice"
    assert reserve[0][2] >= 30


def test_borrow_and_cancellation_block_lesson_access(parent_client, student_client, child, db, monkeypatch):
    result = create_plan(parent_client, child)
    _, slot = prepared(db, result)
    monkeypatch.setattr(runtime.time, "time", lambda: slot["start_ms"] / 1000 + 1)
    delayed = action(student_client, result, slot, "borrow").json()
    assert delayed["slots"][0]["start_ms"] == slot["start_ms"] + 300000
    assert delayed["slots"][0]["preparation"]["status"] == "ready"
    assert action(student_client, result, slot, "cancel").json()["status"] == "cancelled"
    assert (
        parent_client.get("/api/lesson_delivery/" + result["id"] + "/lesson/" + slot["id"]).status_code == 409
    )


def test_a_class_can_be_snoozed_only_once(parent_client, student_client, child, db, monkeypatch):
    result = create_plan(parent_client, child)
    _, slot = prepared(db, result)
    monkeypatch.setattr(runtime.time, "time", lambda: slot["start_ms"] / 1000 + 1)
    first = action(student_client, result, slot, "borrow")
    assert first.status_code == 200
    delayed = first.json()["slots"][0]
    assert delayed["borrowed_minutes"] == 5
    # The class rings again at its new time; a second snooze is refused and changes nothing.
    monkeypatch.setattr(runtime.time, "time", lambda: delayed["start_ms"] / 1000 + 1)
    second = action(student_client, result, slot, "borrow")
    assert second.status_code == 409
    assert "once" in second.json()["detail"]
    unchanged = parent_client.get("/api/lesson_delivery/student/" + child["id"]).json()["timetables"][0][
        "slots"
    ][0]
    assert unchanged["start_ms"] == delayed["start_ms"] and unchanged["borrowed_minutes"] == 5
    # The child can still join once the lesson is ready.
    assert action(student_client, result, slot, "start").status_code == 200


def test_time_save_is_idempotent_and_only_one_active_timetable_exists(parent_client, child):
    first = create_plan(parent_client, child)
    assert create_plan(parent_client, child)["id"] == first["id"]


def test_position_and_finish_require_narration_not_just_api_navigation(
    parent_client, student_client, child, db, monkeypatch
):
    result = create_plan(parent_client, child)
    row, slot = prepared(db, result)
    state = copy.deepcopy(row.state)
    state["slots"][0]["narrated_positions"] = []
    row.state = state
    monkeypatch.setattr(runtime.time, "time", lambda: slot["start_ms"] / 1000 + 1)
    assert action(student_client, result, slot, "start").status_code == 200
    assert action(student_client, result, slot, "position", position=1).status_code == 409


def test_borrow_moves_future_lessons_and_keeps_break_duration(
    parent_client, student_client, child, db, monkeypatch
):
    second = "math_g3_m1_l2_sort_quadrilaterals"
    cards = router.available()
    monkeypatch.setattr(router, "available", lambda: cards + [{**cards[0], "id": second}])
    create_plan(parent_client, child)
    routine = db.get(SchoolRoutine, uuid.UUID(child["id"]))
    previous = db.scalar(select(Timetable).where(Timetable.student_id == routine.student_id))
    previous.status = "cancelled"
    db.flush()
    row = routines.make_timetable(
        db,
        routine,
        [cards[0], {**cards[0], "id": second}],
        routines.next_start("09:00", routines.clock_now()),
    )
    result = runtime.snapshot(row)
    _, slot = prepared(db, result)
    monkeypatch.setattr(runtime.time, "time", lambda: slot["start_ms"] / 1000 + 1)
    delayed = action(student_client, result, slot, "borrow").json()
    for before, after in zip(result["slots"], delayed["slots"], strict=True):
        assert after["start_ms"] - before["start_ms"] == 300000
        assert after["end_ms"] - before["end_ms"] == 300000
    assert delayed["slots"][1]["end_ms"] - delayed["slots"][1]["start_ms"] == 300000


def test_start_time_survives_reload_and_student_cannot_change_it(parent_client, student_client, child, db):
    create_plan(parent_client, child)
    routine = db.get(SchoolRoutine, uuid.UUID(child["id"]))
    assert routine.start_time == "09:00"
    assert (
        student_client.get("/api/lesson_delivery/routine/" + child["id"]).json()["routine"]["start_time"]
        == "09:00"
    )
    assert student_client.get("/api/lesson_delivery/routine/" + str(uuid.uuid4())).status_code == 403
    assert save_time(parent_client, {"id": str(uuid.uuid4())}).status_code == 404


def test_parent_cannot_control_child_class(parent_client, child):
    result = create_plan(parent_client, child)
    for kind in ["start", "borrow", "position", "finish", "cancel", "heartbeat"]:
        assert action(parent_client, result, result["slots"][0], kind).status_code == 403


def test_draft_use_is_an_operator_policy_not_a_parent_setting(parent_client, child, monkeypatch, db):
    monkeypatch.delenv("EDAPTIVE_ALLOW_DRAFT_LESSONS")
    result = save_time(parent_client, child).json()
    assert result["routine"]["status"] == "awaiting_review"
    assert result["timetable"]["slots"][0]["kind"] == "unavailable"
    assert db.get(SchoolRoutine, uuid.UUID(child["id"])).start_time == "09:00"
    monkeypatch.setenv("EDAPTIVE_ALLOW_DRAFT_LESSONS", "1")
    assert save_time(parent_client, child).json()["timetable"]["slots"][0]["concept_id"] == CID


def test_past_school_time_uses_tomorrow_without_parent_date_choice(parent_client, child):
    result = save_time(parent_client, child, start_time="07:00").json()["timetable"]
    at = datetime.fromtimestamp(result["slots"][0]["start_ms"] / 1000, routines.SCHOOL_ZONE)
    assert at.date().isoformat() == "2026-10-15" and at.hour == 7


def test_changed_start_time_moves_future_class_but_preserves_ready_job(parent_client, child, db):
    result = create_plan(parent_client, child)
    _, slot = prepared(db, result)
    changed = save_time(parent_client, child, start_time="10:00").json()["timetable"]
    assert changed["id"] == result["id"]
    assert changed["slots"][0]["job_id"] == slot["job_id"]
    assert changed["slots"][0]["start_ms"] == slot["start_ms"] + 3600000
    assert changed["slots"][0]["prepare_at_ms"] == slot["prepare_at_ms"] + 3600000
    assert changed["slots"][0]["preparation"]["percent"] == 100


def test_daily_worker_plans_next_lesson_for_next_day_after_delivery(
    parent_client, student_client, child, db, monkeypatch
):
    second = "math_g3_m1_l2_sort_quadrilaterals"
    cards = router.available()

    def loader():
        return cards + [{**cards[0], "id": second}]

    monkeypatch.setattr(router, "available", loader)
    result = create_plan(parent_client, child)
    _, slot = prepared(db, result)
    monkeypatch.setattr(runtime.time, "time", lambda: slot["start_ms"] / 1000 + 1)
    for kind, values in [
        ("start", {}),
        ("position", {"position": 1}),
        ("position", {"position": 2}),
        ("finish", {}),
    ]:
        assert action(student_client, result, slot, kind, **values).status_code == 200
    routine = db.get(SchoolRoutine, uuid.UUID(child["id"]))
    following = routines.refresh_routine(db, routine, loader, force=True)
    assert following.state["slots"][0]["concept_id"] == second
    assert following.state["school_date"] == "2026-10-15"
    assert routines.refresh_routine(db, routine, loader).id == following.id


def test_missed_days_reschedule_same_ready_lesson_without_stacking(parent_client, child, db, monkeypatch):
    result = create_plan(parent_client, child)
    row, slot = prepared(db, result)
    monkeypatch.setattr(routines, "clock_now", lambda: datetime(2026, 10, 16, 3, tzinfo=UTC))
    routine = db.get(SchoolRoutine, uuid.UUID(child["id"]))
    recovered = routines.refresh_routine(db, routine, router.available)
    assert recovered.id == row.id
    assert recovered.state["school_date"] == "2026-10-16"
    assert recovered.state["slots"][0]["job_id"] == slot["job_id"]
    assert recovered.state["slots"][0]["preparation"]["percent"] == 100


def test_time_change_does_not_interrupt_running_class(parent_client, student_client, child, db, monkeypatch):
    result = create_plan(parent_client, child)
    _, slot = prepared(db, result)
    monkeypatch.setattr(runtime.time, "time", lambda: slot["start_ms"] / 1000 + 1)
    started = action(student_client, result, slot, "start").json()
    changed = save_time(parent_client, child, start_time="11:00").json()
    assert changed["routine"]["start_time"] == "11:00"
    assert changed["timetable"]["slots"][0]["start_ms"] == started["slots"][0]["start_ms"]
    assert changed["timetable"]["slots"][0]["status"] == "started"


def test_missing_content_saves_time_without_inventing_a_lesson(parent_client, child, monkeypatch):
    monkeypatch.setattr(router, "available", lambda: [])
    result = save_time(parent_client, child).json()
    assert result["routine"]["status"] == "content_unavailable"
    assert result["timetable"]["slots"][0]["kind"] == "unavailable"


def test_outage_saves_time_and_system_retries_automatically(parent_client, child, monkeypatch, db):
    cards = router.available()

    def unavailable():
        raise OSError("lesson service stopped")

    monkeypatch.setattr(router, "available", unavailable)
    result = save_time(parent_client, child).json()
    assert result["routine"]["status"] == "waiting_for_service"
    routine = db.get(SchoolRoutine, uuid.UUID(child["id"]))
    monkeypatch.setattr(routines, "clock_now", lambda: datetime(2026, 10, 14, 3, 1, tzinfo=UTC))
    assert routines.refresh_routine(db, routine, lambda: cards).state["slots"][0]["concept_id"] == CID


def test_parent_cannot_read_another_households_routine_or_mark_narration(parent_client, child):
    assert parent_client.get("/api/lesson_delivery/student/" + str(uuid.uuid4())).status_code == 404
    result = create_plan(parent_client, child)
    assert (
        parent_client.post(
            "/api/lesson_delivery/" + result["id"] + "/narrate",
            json={"slot_id": result["slots"][0]["id"], "segment_id": "s0001", "voice": "af_heart"},
        ).status_code
        == 403
    )


def _voice(monkeypatch, *, job, lesson=None):
    def fake(path, payload=None, timeout=5):
        if path.endswith("/lesson"):
            if lesson is None:
                raise ValueError("The prepared lesson is not ready.")
            return lesson
        return job

    monkeypatch.setattr(runtime, "voice_request", fake)


FINISHED = {"status": "ready", "percent": 100, "message": "Lesson ready", "completed": 84, "total": 84}
LESSON = {"segments": [{"id": "a"}, {"id": "b"}], "timing": TIMING}


def test_a_finished_voice_job_becomes_ready_not_stuck_at_98(
    parent_client, student_client, child, db, monkeypatch
):
    result = create_plan(parent_client, child)
    row = db.get(Timetable, uuid.UUID(result["id"]))
    state = copy.deepcopy(row.state)
    _voice(monkeypatch, job=dict(FINISHED), lesson=LESSON)
    assert runtime.refresh_preparation(state, 0) is False
    slot = state["slots"][0]
    assert slot["preparation"]["status"] == "ready"
    assert slot["preparation"]["percent"] == 100
    assert slot["segment_count"] == 2 and slot["timing"] == TIMING
    # Saved like the worker saves it, the child can now join at class time.
    row.state = state
    db.flush()
    monkeypatch.setattr(runtime.time, "time", lambda: slot["start_ms"] / 1000 + 1)
    assert action(student_client, result, slot, "start").status_code == 200


def test_a_lesson_that_cannot_be_fetched_yet_stays_checking_and_is_retried(
    parent_client, child, db, monkeypatch
):
    result = create_plan(parent_client, child)
    state = copy.deepcopy(db.get(Timetable, uuid.UUID(result["id"])).state)
    _voice(monkeypatch, job=dict(FINISHED), lesson=None)
    with pytest.raises(ValueError):
        runtime.refresh_preparation(state, 0)
    prep = state["slots"][0]["preparation"]
    assert prep["status"] == "checking" and prep["percent"] == 98


def test_a_lesson_still_being_prepared_keeps_the_worker_waiting(parent_client, child, db, monkeypatch):
    result = create_plan(parent_client, child)
    state = copy.deepcopy(db.get(Timetable, uuid.UUID(result["id"])).state)
    _voice(monkeypatch, job={"status": "preparing", "percent": 40, "message": "Working"})
    assert runtime.refresh_preparation(state, 0) is True
    assert state["slots"][0]["preparation"]["status"] == "preparing"
