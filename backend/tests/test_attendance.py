import uuid
from datetime import UTC, datetime

from app.session_log.store import append


def record(
    db, child, *, status="present", reason="completed", percent=100, day="2026-10-14", title="Pairs to ten"
):
    append(
        db,
        {
            "event_id": str(uuid.uuid4()),
            "event_type": "lesson.attendance_recorded",
            "event_version": 1,
            "occurred_at": datetime.now(UTC).isoformat(),
            "source": "lesson_delivery",
            "session_id": None,
            "student_id": child["id"],
            "payload": {
                "timetable_id": str(uuid.uuid4()),
                "slot_id": str(uuid.uuid4()),
                "concept_id": "math_g2_m1_l1_pairs_to_ten",
                "card_version": 2,
                "school_date": day,
                "status": status,
                "reason": reason,
                "attended_percent": percent,
                "lesson_title": title,
            },
        },
    )
    db.flush()


def path(child):
    return "/api/attendance/" + child["id"]


def test_parent_sees_a_dated_log_newest_first_with_totals(parent_client, child, db):
    record(db, child, day="2026-10-13")
    record(db, child, status="absent", reason="left_early", percent=40, day="2026-10-14", title="Add to ten")
    result = parent_client.get(path(child))
    assert result.status_code == 200
    body = result.json()
    assert body["threshold_percent"] == 70
    assert body["summary"] == {"present": 1, "absent": 1}
    assert [r["school_date"] for r in body["records"]] == ["2026-10-14", "2026-10-13"]
    first = body["records"][0]
    assert (first["status"], first["reason"], first["attended_percent"], first["lesson_title"]) == (
        "absent",
        "left_early",
        40,
        "Add to ten",
    )


def test_an_empty_log_is_an_empty_list(parent_client, child):
    body = parent_client.get(path(child)).json()
    assert body["records"] == [] and body["summary"] == {"present": 0, "absent": 0}


def test_each_child_sees_only_their_own_record_in_the_parent_view(parent_client, child, db):
    other = parent_client.post("/api/profiles", json={"display_name": "Noor", "grade": 2}).json()
    record(db, child)
    record(db, other, status="absent", reason="did_not_join", percent=0)
    assert parent_client.get(path(child)).json()["summary"] == {"present": 1, "absent": 0}
    assert parent_client.get(path(other)).json()["summary"] == {"present": 0, "absent": 1}


def test_only_the_parent_can_read_attendance(client, student_client, child):
    assert client.get(path(child)).status_code == 401
    assert student_client.get(path(child)).status_code == 403


def test_unknown_children_are_not_found(parent_client):
    assert parent_client.get("/api/attendance/" + str(uuid.uuid4())).status_code == 404
