import json
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.contracts import ContractError, get_contracts
from app.core.db import get_db
from app.core.identity import (
    Actor,
    CurrentActor,
    ParentActor,
    ensure_student_access,
    install_actor_resolver,
)

HOUSEHOLD = uuid.uuid4()
CHILD, OTHER_CHILD = uuid.uuid4(), uuid.uuid4()
STUDENT = Actor(household_id=HOUSEHOLD, role="student", student_id=CHILD)
PARENT = Actor(household_id=HOUSEHOLD, role="parent", student_id=None)


def make_client(actor: Actor | None, install: bool = True) -> TestClient:
    api = FastAPI()

    @api.get("/me")
    def me(actor: CurrentActor):
        return {"role": actor.role}

    @api.get("/parent-only")
    def parent_only(actor: ParentActor):
        return {"ok": True}

    @api.get("/students/{student_id}")
    def student_data(student_id: uuid.UUID, actor: CurrentActor):
        ensure_student_access(actor, student_id)
        return {"ok": True}

    if install:
        install_actor_resolver(api, lambda request, db: actor)
    api.dependency_overrides[get_db] = lambda: None  # these resolvers never touch the DB
    return TestClient(api)


def test_fails_closed_without_auth_module():
    assert make_client(None, install=False).get("/me").status_code == 401


def test_unidentified_request_is_401():
    assert make_client(None).get("/me").status_code == 401


@pytest.mark.parametrize("actor, expected", [(STUDENT, 403), (PARENT, 200)])
def test_parent_only(actor, expected):
    assert make_client(actor).get("/parent-only").status_code == expected


@pytest.mark.parametrize(
    "actor, student_id, expected",
    [(STUDENT, CHILD, 200), (STUDENT, OTHER_CHILD, 403), (PARENT, OTHER_CHILD, 200)],
)
def test_student_can_only_reach_own_profile(actor, student_id, expected):
    assert make_client(actor).get(f"/students/{student_id}").status_code == expected


def test_student_actor_needs_student_id():
    with pytest.raises(ValueError):
        Actor(household_id=HOUSEHOLD, role="student", student_id=None)


def test_contract_rejects_student_without_profile():
    example = get_contracts().root / "examples" / "auth" / "actor.student.json"
    actor = json.loads(example.read_text()) | {"student_id": None}
    with pytest.raises(ContractError):
        get_contracts().validate("auth/actor.schema.json", actor)
