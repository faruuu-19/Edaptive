import uuid

import pytest
from sqlalchemy import select

from app.modules.consent.models import ConsentDecision


def path(child, suffix=""):
    return "/api/consent/" + child["id"] + suffix


def test_permissions_default_off_and_capture_is_unavailable(parent_client, child):
    result = parent_client.get(path(child))
    assert result.status_code == 200
    assert result.json()["input_available"] is False
    assert result.json()["permissions"] == [
        {"kind": "camera", "granted": False, "decided_at": None, "policy_version": "no-input-v1"},
        {"kind": "microphone", "granted": False, "decided_at": None, "policy_version": "no-input-v1"},
        {"kind": "lesson_alarm", "granted": False, "decided_at": None, "policy_version": "no-input-v1"},
    ]


def test_grant_and_revoke_persist_separately_without_overwriting_history(parent_client, child, db):
    for kind in ["camera", "microphone"]:
        assert parent_client.put(path(child, "/" + kind), json={"granted": True}).status_code == 200
    # Repeating a desired state is an idempotent save, not another consent decision.
    parent_client.put(path(child, "/camera"), json={"granted": True})
    assert parent_client.put(path(child, "/camera"), json={"granted": False}).status_code == 200
    result = parent_client.get(path(child)).json()
    states = {p["kind"]: p for p in result["permissions"] if p["kind"] != "lesson_alarm"}
    assert states["camera"]["granted"] is False and states["microphone"]["granted"] is True
    assert all(p["decided_at"] is not None for p in states.values())
    assert result["input_available"] is False
    history = list(db.scalars(select(ConsentDecision).order_by(ConsentDecision.id)))
    assert [(r.kind, r.granted) for r in history] == [
        ("camera", True),
        ("microphone", True),
        ("camera", False),
    ]
    assert all(r.decided_by == "parent" and r.policy_version == "no-input-v1" for r in history)


def test_anonymous_and_student_cannot_read_or_change_consent(client, student_client, child):
    assert client.get(path(child)).status_code == 401
    assert client.put(path(child, "/camera"), json={"granted": True}).status_code == 401
    assert student_client.get(path(child)).status_code == 403
    assert student_client.put(path(child, "/camera"), json={"granted": True}).status_code == 403


def test_decisions_are_per_child_and_household(parent_client, child):
    other = parent_client.post("/api/profiles", json={"display_name": "Test sibling", "grade": 2}).json()
    parent_client.put(path(child, "/microphone"), json={"granted": True})
    assert not any(p["granted"] for p in parent_client.get(path(other)).json()["permissions"])
    unknown = {"id": str(uuid.uuid4())}
    assert parent_client.get(path(unknown)).status_code == 404
    assert parent_client.put(path(unknown, "/camera"), json={"granted": True}).status_code == 404


def test_archived_child_cannot_receive_new_permissions(parent_client, child):
    assert parent_client.delete("/api/profiles/" + child["id"]).status_code == 204
    assert parent_client.get(path(child)).status_code == 404
    assert parent_client.put(path(child, "/camera"), json={"granted": True}).status_code == 404


@pytest.mark.parametrize("body", [{"granted": "yes"}, {"granted": 1}, {"granted": True, "capture": True}, {}])
def test_consent_requires_only_a_real_boolean(parent_client, child, body):
    assert parent_client.put(path(child, "/camera"), json=body).status_code == 422


def test_unknown_permission_and_deletion_are_not_exposed(parent_client, child):
    assert parent_client.put(path(child, "/attention"), json={"granted": True}).status_code == 422
    assert parent_client.delete(path(child, "/camera")).status_code == 405


def test_parent_allows_the_lesson_alarm_and_the_child_can_only_read_it(
    parent_client, student_client, client, child
):
    assert student_client.get(path(child, "/lesson-alarm")).json() == {"granted": False}
    assert parent_client.put(path(child, "/lesson_alarm"), json={"granted": True}).status_code == 200
    assert student_client.get(path(child, "/lesson-alarm")).json() == {"granted": True}
    assert parent_client.put(path(child, "/lesson_alarm"), json={"granted": False}).status_code == 200
    assert student_client.get(path(child, "/lesson-alarm")).json() == {"granted": False}
    # The control belongs to the parent; a child can neither change it nor read the other permissions.
    assert student_client.put(path(child, "/lesson_alarm"), json={"granted": True}).status_code == 403
    assert student_client.get(path(child)).status_code == 403
    assert client.get(path(child, "/lesson-alarm")).status_code == 401


def test_a_child_cannot_read_another_childs_alarm_setting(parent_client, student_client, child):
    other = parent_client.post("/api/profiles", json={"display_name": "Noor", "grade": 2}).json()
    assert student_client.get(path(other, "/lesson-alarm")).status_code == 403
