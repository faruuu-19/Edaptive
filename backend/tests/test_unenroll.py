"""Unenrolling permanently deletes a child's profile and stored data, and asks for the parent PIN."""

import uuid

import pytest
from sqlalchemy import func, select

from app.modules.consent.models import ConsentDecision
from app.modules.lesson_delivery.models import LearningProgress, SchoolRoutine, Timetable

from .conftest import PARENT_PIN


def unenroll(client, child, pin=PARENT_PIN):
    return client.post(f"/api/profiles/{child['id']}/unenroll", json={"pin": pin})


def give_data(db, parent_client, child, household_id):
    """Rows the child owns across modules."""
    sid = uuid.UUID(child["id"])
    db.add(SchoolRoutine(student_id=sid, household_id=household_id, start_time="09:00"))
    db.add(Timetable(student_id=sid, household_id=household_id, state={"slots": []}))
    db.add(LearningProgress(student_id=sid, household_id=household_id, state={"modules": []}))
    db.flush()
    parent_client.put(f"/api/consent/{child['id']}/camera", json={"granted": True})


def rows_for(db, child):
    sid = uuid.UUID(child["id"])
    return {
        model.__name__: db.scalar(select(func.count()).select_from(model).where(model.student_id == sid))
        for model in (SchoolRoutine, Timetable, LearningProgress, ConsentDecision)
    }


@pytest.fixture
def household_id(parent_client, db):
    from app.core.household import get_household

    return get_household(db).id


def test_a_wrong_pin_keeps_the_child(parent_client, child):
    assert unenroll(parent_client, child, "0000").status_code == 401
    assert [p["id"] for p in parent_client.get("/api/profiles").json()] == [child["id"]]


def test_the_right_pin_deletes_the_profile_and_everything_stored_for_the_child(
    parent_client, child, db, household_id
):
    give_data(db, parent_client, child, household_id)
    assert all(rows_for(db, child).values()), "the child has data to delete"
    assert unenroll(parent_client, child).status_code == 204
    assert parent_client.get("/api/profiles").json() == []
    assert rows_for(db, child) == {
        "SchoolRoutine": 0,
        "Timetable": 0,
        "LearningProgress": 0,
        "ConsentDecision": 0,
    }
    assert parent_client.get(f"/api/attendance/{child['id']}").status_code == 404
    assert parent_client.get(f"/api/consent/{child['id']}").status_code == 404


def test_other_children_keep_their_data(parent_client, child, db, household_id):
    sibling = parent_client.post("/api/profiles", json={"display_name": "Noor", "grade": 1}).json()
    give_data(db, parent_client, sibling, household_id)
    assert unenroll(parent_client, child).status_code == 204
    assert [p["id"] for p in parent_client.get("/api/profiles").json()] == [sibling["id"]]
    assert all(rows_for(db, sibling).values())


def test_only_the_parent_can_unenroll(client, student_client, child):
    assert unenroll(client, child).status_code == 401
    assert unenroll(student_client, child).status_code == 403


@pytest.mark.parametrize("pin", ["", "12", "1234567", "abcd"])
def test_the_pin_must_be_4_to_6_digits(parent_client, child, pin):
    assert unenroll(parent_client, child, pin).status_code == 422


def test_repeated_wrong_pins_lock_out_even_the_right_one(parent_client, child):
    for _ in range(5):
        assert unenroll(parent_client, child, "0000").status_code == 401
    locked = unenroll(parent_client, child, PARENT_PIN)
    assert locked.status_code == 429 and int(locked.headers["Retry-After"]) > 0
    assert len(parent_client.get("/api/profiles").json()) == 1


def test_an_unknown_child_is_not_found(parent_client):
    assert unenroll(parent_client, {"id": str(uuid.uuid4())}).status_code == 404


def test_the_old_one_click_remove_is_gone(parent_client, child):
    assert parent_client.delete(f"/api/profiles/{child['id']}").status_code == 405


def test_a_childs_grade_cannot_be_changed(parent_client, child):
    assert parent_client.patch(f"/api/profiles/{child['id']}", json={"grade": 4}).status_code == 422
    assert (
        parent_client.patch(f"/api/profiles/{child['id']}", json={"display_name": "Zaid"}).json()["grade"]
        == child["grade"]
    )
