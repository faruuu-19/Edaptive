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


def test_missed_days_close_the_lesson_and_plan_one_new_day_without_stacking(
    parent_client, child, db, monkeypatch
):
    result = create_plan(parent_client, child)
    row, slot = prepared(db, result)
    monkeypatch.setattr(routines, "clock_now", lambda: datetime(2026, 10, 16, 3, tzinfo=UTC))
    routine = db.get(SchoolRoutine, uuid.UUID(child["id"]))
    recovered = routines.refresh_routine(db, routine, router.available)
    assert row.status == "completed" and row.state["slots"][0]["status"] == "unfinished"
    assert recovered.id != row.id and recovered.status == "active"
    assert recovered.state["school_date"] == "2026-10-16"
    assert len(timetables_of(db, child)) == 2, "days that passed are not stacked up"


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


# ---- Leaving a live class: the clock never moves, the child's place is saved ----------------------


def started_class(parent_client, student_client, child, db, monkeypatch):
    result = create_plan(parent_client, child)
    _, slot = prepared(db, result)
    monkeypatch.setattr(runtime.time, "time", lambda: slot["start_ms"] / 1000 + 1)
    assert action(student_client, result, slot, "start").status_code == 200
    return result, slot


def day_slots(parent_client, child):
    return parent_client.get("/api/lesson_delivery/student/" + child["id"]).json()["timetables"][0]["slots"]


def delivery_actions(db, child):
    events = db.scalars(select(Event).where(Event.student_id == uuid.UUID(child["id"])).order_by(Event.seq))
    return [
        (e.event_type, e.payload.get("action") or e.payload.get("reason"))
        for e in events
        if e.event_type in {"lesson.delivery_changed", "session.started", "session.ended"}
    ]


def test_leaving_a_class_keeps_the_clock_and_saves_the_place(
    parent_client, student_client, child, db, monkeypatch
):
    result, slot = started_class(parent_client, student_client, child, db, monkeypatch)
    assert action(student_client, result, slot, "position", position=1).status_code == 200
    before = [(s["start_ms"], s["end_ms"]) for s in day_slots(parent_client, child)]
    calls = []
    monkeypatch.setattr(runtime, "voice_request", lambda *a, **k: calls.append(a[0]) or {})
    left = action(student_client, result, slot, "exit")
    assert left.status_code == 200
    out = left.json()["slots"][0]
    assert out["class_phase"] == "exited" and out["position"] == 1
    assert out["exit_count"] == 1 and out["exit_reason"] == "child" and out["exited_at_ms"]
    # Nothing else in the day moves because a child left.
    assert [(s["start_ms"], s["end_ms"]) for s in day_slots(parent_client, child)] == before
    assert any(path.endswith("/release") for path in calls), "leaving must free the teacher voice"
    kinds = delivery_actions(db, child)
    assert ("session.ended", "exited") in kinds and ("lesson.delivery_changed", "exit") in kinds


def test_only_the_child_can_leave_and_only_from_a_running_class(
    parent_client, student_client, child, db, monkeypatch
):
    result = create_plan(parent_client, child)
    _, slot = prepared(db, result)
    for kind in ("exit", "rejoin"):
        assert action(parent_client, result, slot, kind).status_code == 403
    monkeypatch.setattr(runtime.time, "time", lambda: slot["start_ms"] / 1000 + 1)
    assert action(student_client, result, slot, "exit").status_code == 409  # not started yet
    assert action(student_client, result, slot, "rejoin").status_code == 409


def test_a_child_can_rejoin_where_they_stopped_until_class_time_ends(
    parent_client, student_client, child, db, monkeypatch
):
    result, slot = started_class(parent_client, student_client, child, db, monkeypatch)
    assert action(student_client, result, slot, "position", position=1).status_code == 200
    first = day_slots(parent_client, child)[0]["session_id"]
    assert action(student_client, result, slot, "exit").status_code == 200
    calls = []
    monkeypatch.setattr(runtime, "voice_request", lambda *a, **k: calls.append(a[0]) or {"reserved": True})
    back = action(student_client, result, slot, "rejoin")
    assert back.status_code == 200
    out = back.json()["slots"][0]
    assert out["class_phase"] == "started" and out["position"] == 1
    assert out["session_id"] != first and out["exit_count"] == 1
    assert any(path.endswith("/reserve") for path in calls)
    assert len([k for k in delivery_actions(db, child) if k[0] == "session.started"]) == 2


def test_after_class_time_ends_the_lesson_is_left_early_and_cannot_be_rejoined(
    parent_client, student_client, child, db, monkeypatch
):
    result, slot = started_class(parent_client, student_client, child, db, monkeypatch)
    assert action(student_client, result, slot, "exit").status_code == 200
    end = day_slots(parent_client, child)[0]["end_ms"]
    monkeypatch.setattr(runtime.time, "time", lambda: end / 1000 + 1)
    assert day_slots(parent_client, child)[0]["class_phase"] != "exited"
    late = action(student_client, result, slot, "rejoin")
    assert late.status_code == 409 and "next school day" in late.json()["detail"]
    after = parent_client.get("/api/lesson_delivery/student/" + child["id"]).json()["timetables"][0]
    assert after["slots"][0]["class_phase"] == "unfinished"


def test_a_child_can_leave_at_most_twice(parent_client, student_client, child, db, monkeypatch):
    result, slot = started_class(parent_client, student_client, child, db, monkeypatch)
    assert action(student_client, result, slot, "exit").status_code == 200
    assert action(student_client, result, slot, "rejoin").status_code == 200
    second = action(student_client, result, slot, "exit")
    assert second.status_code == 200 and second.json()["slots"][0]["class_phase"] == "unfinished"
    assert action(student_client, result, slot, "rejoin").status_code == 409


def test_a_lost_connection_counts_as_leaving(parent_client, student_client, child, db, monkeypatch):
    result, slot = started_class(parent_client, student_client, child, db, monkeypatch)
    row = db.get(Timetable, uuid.UUID(result["id"]))
    now = slot["start_ms"] + 1000
    assert runtime.expire_disconnected(db, row, now + 30_000) is False  # a quiet half minute is fine
    assert runtime.expire_disconnected(db, row, now + runtime.DISCONNECT_MS + 5_000) is True
    out = runtime.snapshot(row, now + runtime.DISCONNECT_MS + 5_000)["slots"][0]
    assert out["exit_reason"] == "timeout" and out["exit_count"] == 1 and out["class_phase"] == "exited"
    assert ("session.ended", "timeout") in delivery_actions(db, child)


# ---- Attendance: present when the child stays for at least 70% of the lesson ----------------------


def attendance_events(db, child):
    events = db.scalars(
        select(Event)
        .where(Event.student_id == uuid.UUID(child["id"]), Event.event_type == "lesson.attendance_recorded")
        .order_by(Event.seq)
    )
    return [e.payload for e in events]


def set_progress(db, result, parts, total=10, **extra):
    """Pretend the child has listened to `parts` of `total` lesson parts."""
    row = db.get(Timetable, uuid.UUID(result["id"]))
    state = copy.deepcopy(row.state)
    state["slots"][0].update(segment_count=total, narrated_positions=list(range(parts)), **extra)
    row.state = state
    db.flush()
    return row


def test_finishing_the_lesson_marks_the_child_present(parent_client, student_client, child, db, monkeypatch):
    result, slot = started_class(parent_client, student_client, child, db, monkeypatch)
    assert action(student_client, result, slot, "position", position=1).status_code == 200
    assert action(student_client, result, slot, "position", position=2).status_code == 200
    assert attendance_events(db, child) == []  # nothing is final until the class is over
    assert action(student_client, result, slot, "finish").status_code == 200
    (record,) = attendance_events(db, child)
    assert record["status"] == "present" and record["reason"] == "completed"
    assert record["attended_percent"] == 100 and record["lesson_title"] == "Polygons"
    assert record["school_date"] == "2026-10-14" and record["slot_id"] == slot["id"]


@pytest.mark.parametrize(
    ("parts", "status", "reason"),
    [
        (6, "absent", "left_early"),
        (7, "present", "left_after_threshold"),
        (9, "present", "left_after_threshold"),
    ],
)
def test_leaving_is_present_only_from_70_percent_and_is_settled_when_class_time_ends(
    parent_client, student_client, child, db, monkeypatch, parts, status, reason
):
    result, slot = started_class(parent_client, student_client, child, db, monkeypatch)
    row = set_progress(db, result, parts)
    assert action(student_client, result, slot, "exit").status_code == 200
    assert attendance_events(db, child) == [], "the child can still rejoin, so it is not final yet"
    end = row.state["slots"][0]["end_ms"]
    assert runtime.settle_due(db, row, end - 1000) is False
    assert runtime.settle_due(db, row, end + 1000) is True
    (record,) = attendance_events(db, child)
    assert (record["status"], record["reason"], record["attended_percent"]) == (status, reason, parts * 10)
    assert runtime.settle_due(db, row, end + 2000) is False, "a class is recorded once"
    assert len(attendance_events(db, child)) == 1


def test_the_second_exit_settles_attendance_at_once(parent_client, student_client, child, db, monkeypatch):
    result, slot = started_class(parent_client, student_client, child, db, monkeypatch)
    set_progress(db, result, 3)
    assert action(student_client, result, slot, "exit").status_code == 200
    assert action(student_client, result, slot, "rejoin").status_code == 200
    assert action(student_client, result, slot, "exit").status_code == 200
    (record,) = attendance_events(db, child)
    assert record["status"] == "absent" and record["attended_percent"] == 30


def test_leaving_then_rejoining_and_finishing_counts_the_whole_class_once(
    parent_client, student_client, child, db, monkeypatch
):
    result, slot = started_class(parent_client, student_client, child, db, monkeypatch)
    assert action(student_client, result, slot, "exit").status_code == 200
    assert action(student_client, result, slot, "rejoin").status_code == 200
    assert action(student_client, result, slot, "position", position=1).status_code == 200
    assert action(student_client, result, slot, "position", position=2).status_code == 200
    assert action(student_client, result, slot, "finish").status_code == 200
    row = db.get(Timetable, uuid.UUID(result["id"]))
    runtime.settle_due(db, row, slot["end_ms"] + 60_000)
    (record,) = attendance_events(db, child)
    assert record["status"] == "present" and record["reason"] == "completed"


# ---- A class that could not run is not the child's absence ----------------------------------------


@pytest.mark.parametrize("preparation", ["waiting", "paused", "checking", "failed", "cancelled"])
def test_a_lesson_that_was_never_ready_is_not_held_and_not_logged_as_absent(
    parent_client, child, db, monkeypatch, preparation
):
    result = create_plan(parent_client, child)
    row = db.get(Timetable, uuid.UUID(result["id"]))
    state = copy.deepcopy(row.state)
    state["slots"][0]["preparation"] = {"status": preparation, "percent": 3}
    row.state = state
    db.flush()
    monkeypatch.setattr(routines, "clock_now", lambda: datetime(2026, 10, 15, 3, 0, tzinfo=UTC))
    routine = db.get(SchoolRoutine, uuid.UUID(child["id"]))
    routines.refresh_routine(db, routine, cards_loader=lambda: router.available())
    assert attendance_events(db, child) == [], "no lesson was ready, so nobody was absent"
    carried = db.get(Timetable, uuid.UUID(result["id"])).state["slots"][0]
    assert carried["status"] == "planned" and "attendance" not in carried, "it is simply tried again tomorrow"
    routines.refresh_routine(db, routine, cards_loader=lambda: router.available(), force=True)
    assert attendance_events(db, child) == []


# ---- A class that could not run moves to the next school day; its lesson is prepared on schedule --------

AFTER_CLASS = datetime(2026, 10, 14, 10, 0, tzinfo=UTC)  # 15:00 in Pakistan: the 09:00 class is over


def unrun_class(db, result, preparation):
    row = db.get(Timetable, uuid.UUID(result["id"]))
    state = copy.deepcopy(row.state)
    state["slots"][0]["preparation"] = preparation
    row.state = state
    db.flush()
    return state["slots"][0]


def refresh_at(db, child, monkeypatch, now):
    monkeypatch.setattr(routines, "clock_now", lambda: now)
    routine = db.get(SchoolRoutine, uuid.UUID(child["id"]))
    routines.refresh_routine(db, routine, cards_loader=lambda: router.available())


def test_a_ready_lesson_stays_on_its_day_so_the_child_can_still_join_late(
    parent_client, child, db, monkeypatch
):
    result = create_plan(parent_client, child)
    _, old = prepared(db, result)
    refresh_at(db, child, monkeypatch, AFTER_CLASS)
    row = db.get(Timetable, uuid.UUID(result["id"]))
    assert row.state["school_date"] == "2026-10-14" and row.state["slots"][0]["start_ms"] == old["start_ms"]
    assert attendance_events(db, child) == [], "absence is only decided at the end of the school day"


def test_a_class_that_is_not_over_yet_is_not_moved(parent_client, child, db, monkeypatch):
    result = create_plan(parent_client, child)
    old = unrun_class(db, result, {"status": "cancelled", "percent": 3})
    refresh_at(db, child, monkeypatch, datetime(2026, 10, 14, 3, 0, tzinfo=UTC))  # 08:00, before class
    slot = db.get(Timetable, uuid.UUID(result["id"])).state["slots"][0]
    assert slot["start_ms"] == old["start_ms"] and slot["job_id"] == old["job_id"]


# ---- Preparation follows the timetable: a job that started too early is held until its time ----------


@pytest.mark.parametrize("status", ["queued", "preparing", "paused"])
def test_a_job_that_started_before_its_preparation_time_is_cancelled_and_made_again_on_time(
    parent_client, child, db, status
):
    """E.g. the parent moved the class later after preparation had already begun."""
    result = create_plan(parent_client, child)
    old = unrun_class(db, result, {"status": status, "percent": 14})
    state = copy.deepcopy(db.get(Timetable, uuid.UUID(result["id"])).state)
    early = old["prepare_at_ms"] - 60_000
    assert runtime.hold_early_jobs(state, early) == [old["job_id"]]
    slot = state["slots"][0]
    assert slot["job_id"] != old["job_id"], "the early job is not reused"
    assert slot["preparation"]["status"] == "waiting" and slot["preparation"]["percent"] == 0


@pytest.mark.parametrize(
    ("status", "when"),
    [
        ("preparing", "on_time"),
        ("paused", "on_time"),
        ("ready", "early"),
        ("checking", "early"),
        ("waiting", "early"),
        ("failed", "early"),
        ("cancelled", "early"),
    ],
)
def test_jobs_are_left_alone_when_it_is_time_or_there_is_nothing_to_hold(
    parent_client, child, db, status, when
):
    result = create_plan(parent_client, child)
    old = unrun_class(db, result, {"status": status, "percent": 50})
    state = copy.deepcopy(db.get(Timetable, uuid.UUID(result["id"])).state)
    now = old["prepare_at_ms"] + (1000 if when == "on_time" else -60_000)
    assert runtime.hold_early_jobs(state, now) == []
    assert state["slots"][0]["job_id"] == old["job_id"]
    assert state["slots"][0]["preparation"]["status"] == status


def test_a_started_class_is_never_held(parent_client, student_client, child, db, monkeypatch):
    result, slot = started_class(parent_client, student_client, child, db, monkeypatch)
    state = copy.deepcopy(db.get(Timetable, uuid.UUID(result["id"])).state)
    assert runtime.hold_early_jobs(state, slot["prepare_at_ms"] - 60_000) == []


# ---- A lesson never comes back: an unfinished class is closed and tomorrow brings the next lesson ----


def two_lessons(monkeypatch):
    second = "math_g3_m1_l2_sort_quadrilaterals"
    cards = router.available()
    monkeypatch.setattr(router, "available", lambda: cards + [{**cards[0], "id": second}])
    return second


def timetables_of(db, child):
    rows = db.scalars(select(Timetable).where(Timetable.student_id == uuid.UUID(child["id"])))
    # created_at is the transaction time in tests, so order by the school day each timetable belongs to
    return sorted(rows, key=lambda row: row.state["school_date"])


NEXT_DAY = datetime(2026, 10, 15, 3, 0, tzinfo=UTC)  # 08:00 in Pakistan, the morning after


def test_a_lesson_left_early_is_closed_and_the_next_day_brings_the_next_lesson(
    parent_client, student_client, child, db, monkeypatch
):
    second = two_lessons(monkeypatch)
    result, slot = started_class(parent_client, student_client, child, db, monkeypatch)
    set_progress(db, result, 5)  # left at 50%
    assert action(student_client, result, slot, "exit").status_code == 200
    refresh_at(db, child, monkeypatch, NEXT_DAY)
    today, tomorrow = timetables_of(db, child)
    assert today.status == "completed" and today.state["slots"][0]["status"] == "unfinished"
    assert tomorrow.status == "active" and tomorrow.state["slots"][0]["concept_id"] == second
    assert tomorrow.state["slots"][0]["position"] == 0, "the new lesson starts from its beginning"
    (record,) = attendance_events(db, child)
    assert (record["status"], record["reason"], record["attended_percent"]) == ("absent", "left_early", 50)


def test_a_class_never_joined_is_absent_at_the_end_of_the_day_and_the_lesson_does_not_return(
    parent_client, child, db, monkeypatch
):
    second = two_lessons(monkeypatch)
    result = create_plan(parent_client, child)
    prepared(db, result)
    refresh_at(db, child, monkeypatch, NEXT_DAY)
    refresh_at(db, child, monkeypatch, NEXT_DAY)  # a second pass changes nothing
    (record,) = attendance_events(db, child)
    assert (record["status"], record["reason"], record["attended_percent"]) == ("absent", "did_not_join", 0)
    assert record["school_date"] == "2026-10-14"
    today, tomorrow = timetables_of(db, child)
    assert today.state["slots"][0]["status"] == "unfinished" and today.status == "completed"
    assert tomorrow.state["slots"][0]["concept_id"] == second


def test_progress_counts_an_unfinished_lesson_as_taken_so_the_plan_moves_on(
    parent_client, student_client, child, db, monkeypatch
):
    second = two_lessons(monkeypatch)
    result, slot = started_class(parent_client, student_client, child, db, monkeypatch)
    assert action(student_client, result, slot, "exit").status_code == 200
    assert action(student_client, result, slot, "rejoin").status_code == 200
    assert action(student_client, result, slot, "exit").status_code == 200  # second exit: class over
    row = timetables_of(db, child)[0]
    assert row.state["slots"][0]["status"] == "unfinished" and row.status == "completed"
    refresh_at(db, child, monkeypatch, datetime(2026, 10, 14, 10, 0, tzinfo=UTC))
    progress = parent_client.get("/api/lesson_delivery/student/" + child["id"]).json()["learning_progress"]
    assert progress["next_required"]["concept_id"] == second
    module = progress["modules"][0]
    assert module["delivered_lessons"] == 0 and module["unfinished_lessons"] == 1


def test_changing_the_start_time_during_the_day_never_logs_an_absence(parent_client, child, db):
    result = create_plan(parent_client, child)
    prepared(db, result)
    assert save_time(parent_client, child, start_time="10:00").status_code == 200
    assert attendance_events(db, child) == []
    assert timetables_of(db, child)[0].state["slots"][0]["status"] == "planned"


@pytest.mark.parametrize("dead", ["cancelled", "failed"])
def test_a_lesson_that_was_never_ready_is_tried_again_with_a_fresh_job_when_the_day_ends(
    parent_client, child, db, monkeypatch, dead
):
    result = create_plan(parent_client, child)
    old = unrun_class(db, result, {"status": dead, "percent": 3})
    refresh_at(db, child, monkeypatch, NEXT_DAY)
    (row,) = timetables_of(db, child)
    slot = row.state["slots"][0]
    assert slot["status"] == "planned" and slot["job_id"] != old["job_id"]
    assert slot["preparation"]["status"] == "waiting" and row.state["school_date"] == "2026-10-15"
    assert attendance_events(db, child) == [], "nobody was absent: no lesson was ever ready"


def preparing(db, response, percent, **extra):
    row = db.get(Timetable, uuid.UUID(response["id"]))
    state = copy.deepcopy(row.state)
    slot = state["slots"][0]
    slot["preparation"] = {"status": "preparing", "percent": percent, **extra}
    row.state = state
    db.flush()
    return row, slot


def student_view(client, child):
    return client.get("/api/lesson_delivery/student/" + child["id"]).json()["timetables"][0]


def test_a_class_that_is_not_ready_at_its_time_is_delayed_and_both_are_told(
    parent_client, student_client, child, db, monkeypatch
):
    result = create_plan(parent_client, child)
    _, slot = preparing(db, result, 50)
    lead = slot["start_ms"] - slot["prepare_at_ms"]
    now = slot["start_ms"] + 1000
    monkeypatch.setattr(runtime.time, "time", lambda: now / 1000)
    view = student_view(student_client, child)
    first, after_break = view["slots"][0], view["slots"][1]
    # Half done after a `lead`-long head start, so about `lead` is still needed.
    delay = first["start_ms"] - slot["start_ms"]
    assert delay >= lead * 0.9 and delay % 300000 == 0, "rounded up to whole five minutes"
    assert first["class_phase"] == "waiting" and first["delay_minutes"] == delay / 60000
    assert "will start at" in first["delay_notice"] and "instead of" in first["delay_notice"]
    assert after_break["start_ms"] - slot["end_ms"] > 0 and view["status"] == "active"
    assert first["status"] == "planned", "a delayed class is not skipped, closed or absent"
    assert attendance_events(db, child) == []
    assert (
        parent_client.get("/api/lesson_delivery/student/" + child["id"]).json()["timetables"][0]["slots"][0][
            "delay_notice"
        ]
        == first["delay_notice"]
    )


def test_a_delay_shifts_every_later_slot_and_keeps_the_lesson(
    parent_client, student_client, child, db, monkeypatch
):
    result = create_plan(parent_client, child)
    row, slot = preparing(db, result, 10)
    before = [(s["start_ms"], s["end_ms"]) for s in row.state["slots"]]
    monkeypatch.setattr(runtime.time, "time", lambda: (slot["start_ms"] + 1) / 1000)
    view = student_view(student_client, child)
    shifted = {s["start_ms"] - b[0] for s, b in zip(view["slots"], before, strict=True)}
    assert len(shifted) == 1 and shifted.pop() > 0, "the whole day moves by the same amount"
    assert (
        view["slots"][0]["concept_id"] == slot["concept_id"] and view["slots"][0]["job_id"] == slot["job_id"]
    )


def test_a_delayed_class_that_is_still_not_ready_is_delayed_again(
    parent_client, student_client, child, db, monkeypatch
):
    result = create_plan(parent_client, child)
    _, slot = preparing(db, result, 50)
    monkeypatch.setattr(runtime.time, "time", lambda: (slot["start_ms"] + 1) / 1000)
    first = student_view(student_client, child)["slots"][0]
    monkeypatch.setattr(runtime.time, "time", lambda: (first["start_ms"] + 1) / 1000)
    second = student_view(student_client, child)["slots"][0]
    assert second["start_ms"] > first["start_ms"]
    assert second["delay_minutes"] > first["delay_minutes"]
    assert second["delayed_from_ms"] == slot["start_ms"], "the notice still names the time it was first due"


def test_a_ready_class_is_never_delayed(parent_client, student_client, child, db, monkeypatch):
    result = create_plan(parent_client, child)
    _, slot = prepared(db, result)
    monkeypatch.setattr(runtime.time, "time", lambda: (slot["start_ms"] + 1) / 1000)
    view = student_view(student_client, child)["slots"][0]
    assert view["start_ms"] == slot["start_ms"] and "delay_notice" not in view
    assert view["class_phase"] == "ringing"


def test_a_class_is_not_delayed_before_its_time(parent_client, student_client, child, db, monkeypatch):
    result = create_plan(parent_client, child)
    _, slot = preparing(db, result, 5)
    monkeypatch.setattr(runtime.time, "time", lambda: (slot["start_ms"] - 60000) / 1000)
    view = student_view(student_client, child)["slots"][0]
    assert view["start_ms"] == slot["start_ms"] and "delay_notice" not in view


def test_a_failed_preparation_is_not_waited_for(parent_client, student_client, child, db, monkeypatch):
    result = create_plan(parent_client, child)
    row = db.get(Timetable, uuid.UUID(result["id"]))
    state = copy.deepcopy(row.state)
    state["slots"][0]["preparation"] = {"status": "failed", "percent": 30}
    row.state = state
    db.flush()
    monkeypatch.setattr(runtime.time, "time", lambda: (state["slots"][0]["start_ms"] + 1) / 1000)
    view = student_view(student_client, child)["slots"][0]
    assert view["start_ms"] == state["slots"][0]["start_ms"] and "delay_notice" not in view


def test_a_delay_does_not_use_up_the_childs_snooze(parent_client, student_client, child, db, monkeypatch):
    result = create_plan(parent_client, child)
    _, slot = preparing(db, result, 50)
    monkeypatch.setattr(runtime.time, "time", lambda: (slot["start_ms"] + 1) / 1000)
    view = student_view(student_client, child)["slots"][0]
    assert view.get("borrowed_minutes", 0) == 0
