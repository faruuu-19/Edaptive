"""A new profile starts empty, and each grade is planned from its own lessons (real catalog, no stubs)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.modules.lesson_delivery import router, routines, runtime

MANIFEST = json.loads((Path(__file__).resolve().parents[2] / "docs/content/lesson-pairs.json").read_text())
TIMING = {"minutes": 15, "basis": "card_plan", "buffer_seconds": 180, "estimated": True}


def real_cards():
    """What the voice service lists: one entry per concept/assessment pair in the manifest."""
    return [
        {
            "id": p["concept_id"],
            "grade": p["grade"],
            "module": p["module"],
            "title": p["concept_id"].split("_", 4)[-1].replace("_", " ").capitalize(),
            "card_version": p["concept_version"],
            "ready_for_delivery": False,
            "estimated_minutes": 15,
            "timing": TIMING,
        }
        for p in MANIFEST["pairs"]
    ]


@pytest.fixture(autouse=True)
def real_catalog(monkeypatch):
    monkeypatch.setenv("EDAPTIVE_ALLOW_DRAFT_LESSONS", "1")
    monkeypatch.setattr(router, "available", real_cards)
    monkeypatch.setattr(routines, "clock_now", lambda: datetime(2026, 10, 14, 3, 0, tzinfo=UTC))
    monkeypatch.setattr(runtime, "voice_request", lambda *a, **k: {"reserved": True})


def plan(parent_client, grade):
    child = parent_client.post("/api/profiles", json={"display_name": f"G{grade}", "grade": grade}).json()
    saved = parent_client.put(
        "/api/lesson_delivery/routine/" + child["id"], json={"start_time": "09:00"}
    ).json()
    return child, saved


def test_a_new_profile_has_no_plan_progress_or_attendance(parent_client, child):
    body = parent_client.get("/api/lesson_delivery/student/" + child["id"]).json()
    assert body["timetables"] == [] and body["routine"] is None and body["learning_progress"] is None
    log = parent_client.get("/api/attendance/" + child["id"]).json()
    assert log["records"] == [] and log["summary"] == {"present": 0, "absent": 0}


@pytest.mark.parametrize(
    ("grade", "first_lesson"),
    [(1, "math_g1_m1_l1_embedded_numbers"), (2, "math_g2_m1_l1_pairs_to_ten")],
)
def test_each_grade_is_planned_from_its_own_first_lesson(parent_client, grade, first_lesson):
    child, saved = plan(parent_client, grade)
    lesson = saved["timetable"]["slots"][0]
    assert lesson["kind"] == "lesson" and lesson["concept_id"] == first_lesson
    assert (lesson["module"], lesson["lesson"]) == (1, 1)
    progress = parent_client.get("/api/lesson_delivery/student/" + child["id"]).json()["learning_progress"]
    assert progress["grade"] == grade
    assert progress["next_required"]["concept_id"] == first_lesson


def test_a_grade_without_its_first_lesson_gets_no_other_grades_lesson(parent_client):
    child, saved = plan(parent_client, 3)
    first = saved["timetable"]["slots"][0]
    assert first["kind"] == "unavailable", "never fall back to another grade's lesson"
    assert saved["routine"]["status"] == "content_unavailable"
    assert "Module 1, Lesson 1" in saved["routine"]["message"]
    assert not any(s.get("concept_id", "").startswith("math_g2") for s in saved["timetable"]["slots"])
