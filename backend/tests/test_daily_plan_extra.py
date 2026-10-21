import copy
import uuid
from datetime import UTC, datetime

import pytest

from app.modules.lesson_delivery import curriculum, routines, runtime
from app.modules.lesson_delivery.models import LearningProgress, SchoolRoutine

FIRST = "math_g3_m1_l1_first"
THIRD = "math_g3_m1_l3_third"


@pytest.fixture
def plan(parent_client, child, db, monkeypatch):
    monkeypatch.setenv("EDAPTIVE_ALLOW_DRAFT_LESSONS", "1")
    from app.core.household import StudentProfile

    profile = db.get(StudentProfile, uuid.UUID(child["id"]))
    routine = SchoolRoutine(student_id=profile.id, household_id=profile.household_id, start_time="09:00")
    db.add(routine)
    db.flush()
    card = {
        "id": FIRST,
        "grade": 3,
        "module": 1,
        "title": "First lesson",
        "card_version": 1,
        "ready_for_delivery": False,
        "recommended_prepare_minutes": 15,
    }
    monkeypatch.setattr(
        curriculum,
        "module_index",
        lambda *args: [{"module": 1, "expected": 3, "lessons": {1: FIRST, 3: THIRD}}],
    )
    monkeypatch.setattr(routines, "clock_now", lambda: datetime(2026, 10, 14, 3, tzinfo=UTC))
    row = routines.refresh_routine(db, routine, lambda: [card], force=True)
    return row, routine, card


def test_real_day_has_four_classes_and_separate_breaks_with_no_inactive_alarms(plan):
    row, _, _ = plan
    state = row.state
    assert [s["subject"] for s in state["slots"]] == [
        "math",
        "break",
        "science",
        "break",
        "english",
        "break",
        "physical",
    ]
    for previous, following in zip(state["slots"], state["slots"][1:], strict=False):
        assert previous["end_ms"] == following["start_ms"]
    for slot in state["slots"]:
        assert slot["end_ms"] - slot["start_ms"] == (5 if slot["kind"] == "break" else 20) * 60000
        if slot["subject"] in ["science", "english", "physical"]:
            assert "job_id" not in slot and slot["status"] == "coming_soon"
    result = runtime.snapshot(row, now=state["slots"][-1]["end_ms"] + 1)
    assert all(s["class_phase"] == "coming_soon" for s in result["slots"] if s["kind"] == "unavailable")


def test_prepared_script_keeps_twenty_minute_class_and_later_breaks(plan):
    row, _, _ = plan
    state = copy.deepcopy(row.state)
    before = copy.deepcopy(state)
    runtime.apply_prepared(
        state,
        0,
        {
            "segments": [{"id": "s1"}],
            "timing": {"minutes": 31, "buffer_seconds": 180, "basis": "prepared_script"},
        },
        {"status": "ready", "percent": 100},
    )
    assert state["slots"][0]["end_ms"] - state["slots"][0]["start_ms"] == 20 * 60000
    for earlier, later in zip(before["slots"][1:], state["slots"][1:], strict=True):
        assert later["start_ms"] - earlier["start_ms"] == 0
        assert later["end_ms"] - earlier["end_ms"] == 0
    assert state["slots"][1]["end_ms"] - state["slots"][1]["start_ms"] == 5 * 60000


def test_completed_lesson_persists_and_next_available_pair_is_planned(plan, db):
    row, routine, card = plan
    state = copy.deepcopy(row.state)
    state["slots"][0]["status"] = "completed"
    row.state = state
    row.status = "completed"
    db.flush()
    next_day = routines.refresh_routine(db, routine, lambda: [card, {**card, "id": THIRD}], force=True)
    assert next_day.state["slots"][0]["concept_id"] == THIRD
    saved = db.get(LearningProgress, routine.student_id).state
    assert saved["next_required"]["lesson"] == 3 and saved["next_required"]["matched"] is True
    assert saved["modules"][0]["lessons"][1]["matched"] is False
    assert saved["modules"][0]["status"] == "in_progress" and saved["modules"][0]["delivered_lessons"] == 1
    assert saved["mastery_assessed"] is False


def test_new_pair_activates_existing_placeholder_in_place(plan, db):
    row, routine, card = plan
    state = copy.deepcopy(row.state)
    state["slots"][0]["status"] = "completed"
    row.state = state
    row.status = "completed"
    db.flush()
    next_day = routines.refresh_routine(db, routine, lambda: [card], force=True)
    identity = next_day.id
    slot_id = next_day.state["slots"][0]["id"]
    second = {**card, "id": "math_g3_m1_l2_second"}
    modules = [{"module": 1, "expected": 3, "lessons": {1: FIRST, 2: second["id"], 3: THIRD}}]
    from unittest.mock import patch

    with patch.object(curriculum, "module_index", return_value=modules):
        activated = routines.refresh_routine(db, routine, lambda: [card, second], force=True)
    assert activated.id == identity and activated.state["slots"][0]["id"] == slot_id
    assert activated.state["slots"][0]["kind"] == "lesson"
    assert activated.state["slots"][0]["concept_id"] == second["id"]


def test_partial_contiguous_export_cannot_confirm_module_complete(tmp_path, monkeypatch):
    grade = tmp_path / "grade3"
    grade.mkdir()
    (grade / "math_g3_m1_Lessons.json").write_text(
        '[{"concept_id":"math_g3_m1_l1_first","card_version":1},{"concept_id":"math_g3_m1_l2_second","card_version":1}]'
    )
    monkeypatch.setattr(curriculum, "ROOT", tmp_path)
    assert curriculum.module_index(3, [])[0]["expected"] is None


def test_next_pair_can_cross_module_gap_without_leaving_the_grade(parent_client, child, db, monkeypatch):
    from app.core.household import StudentProfile

    profile = db.get(StudentProfile, uuid.UUID(child["id"]))
    profile.grade = 1
    first = "math_g1_m1_l1_first"
    later = "math_g1_m2_l1_later"
    other_grade = "math_g2_m1_l1_other"
    monkeypatch.setattr(
        curriculum,
        "module_index",
        lambda *args: [
            {"module": 1, "expected": 3, "lessons": {1: first}},
            {"module": 2, "expected": 2, "lessons": {1: later}},
        ],
    )
    cards = [{"id": cid} for cid in (first, later, other_grade)]
    routine = SchoolRoutine(student_id=profile.id, household_id=profile.household_id, start_time="09:00")
    db.add(routine)
    db.flush()
    progress = curriculum.synchronize(db, routine.household_id, routine.student_id, 1, cards)
    assert progress["next_required"]["concept_id"] == first
    curriculum.mark_delivered(db, routine.student_id, first)
    progress = db.get(LearningProgress, routine.student_id).state
    assert progress["next_required"] == {
        "module": 2,
        "lesson": 1,
        "concept_id": later,
        "matched": True,
    }
    assert progress["modules"][0]["lessons"][1]["matched"] is False
    assert progress["modules"][0]["coverage_confirmed"] is True
