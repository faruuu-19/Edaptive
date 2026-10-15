import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, StrictBool
from sqlalchemy import select

from app.core.db import DbSession
from app.core.household import StudentProfile, get_active_profile
from app.core.identity import ParentActor

from .models import ConsentDecision

router = APIRouter()
KINDS = ("camera", "microphone")


class ConsentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    granted: StrictBool


def require_child(db, actor, student_id, lock=False):
    profile = (
        db.scalar(
            select(StudentProfile)
            .where(
                StudentProfile.id == student_id,
                StudentProfile.household_id == actor.household_id,
                StudentProfile.archived_at.is_(None),
            )
            .with_for_update()
        )
        if lock
        else get_active_profile(db, actor.household_id, student_id)
    )
    if not profile:
        raise HTTPException(404, "Profile not found.")


def latest(db, actor, student_id, kind):
    return db.scalar(
        select(ConsentDecision)
        .where(
            ConsentDecision.student_id == student_id,
            ConsentDecision.household_id == actor.household_id,
            ConsentDecision.kind == kind,
        )
        .order_by(ConsentDecision.id.desc())
        .limit(1)
    )


def snapshot(db, actor, student_id):
    permissions = []
    for kind in KINDS:
        decision = latest(db, actor, student_id, kind)
        permissions.append(
            {
                "kind": kind,
                "granted": decision.granted if decision else False,
                "decided_at": decision.decided_at.isoformat() if decision else None,
                "policy_version": decision.policy_version if decision else "no-input-v1",
            }
        )
    return {"student_id": str(student_id), "permissions": permissions, "input_available": False}


@router.get("/{student_id}")
def get_permissions(student_id: uuid.UUID, actor: ParentActor, db: DbSession):
    require_child(db, actor, student_id)
    return snapshot(db, actor, student_id)


@router.put("/{student_id}/{kind}")
def decide(
    student_id: uuid.UUID,
    kind: Literal["camera", "microphone"],
    body: ConsentInput,
    actor: ParentActor,
    db: DbSession,
):
    require_child(db, actor, student_id, lock=True)
    previous = latest(db, actor, student_id, kind)
    if previous is None or previous.granted != body.granted:
        # Append instead of overwriting the previous decision. This records guardian
        # intent only; there is no media API, capture process or uploaded stream.
        db.add(
            ConsentDecision(
                student_id=student_id, household_id=actor.household_id, kind=kind, granted=body.granted
            )
        )
        db.flush()
    return snapshot(db, actor, student_id)
