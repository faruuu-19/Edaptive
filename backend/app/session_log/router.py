import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Query, status

from app.core.contracts import ContractError
from app.core.db import DbSession
from app.core.identity import CurrentActor, ensure_student_access
from app.session_log import store

router = APIRouter(prefix="/api/events", tags=["session-log"])


@router.post("", status_code=201)
def append_event(
    db: DbSession,
    actor: CurrentActor,
    event: Annotated[dict[str, Any], Body(description="EventEnvelope (contracts/events)")],
) -> dict[str, int]:
    # A student may only log events about themselves; a parent may log for any of their children.
    student_id = event.get("student_id") if isinstance(event, dict) else None
    if actor.role == "student" and student_id != str(actor.student_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "students can only log their own events")
    try:
        return {"seq": store.append(db, event)}
    except ContractError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from None


@router.get("")
def list_events(
    db: DbSession,
    actor: CurrentActor,
    session_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
    event_type: Annotated[list[str] | None, Query()] = None,
    after_seq: int = 0,
    limit: Annotated[int, Query(le=1000)] = 500,
) -> list[dict[str, Any]]:
    if actor.role == "student":
        if student_id is not None:
            ensure_student_access(actor, student_id)
        student_id = actor.student_id
    events = store.read(
        db,
        session_id=session_id,
        student_id=student_id,
        event_types=event_type,
        after_seq=after_seq,
        limit=limit,
    )
    return [{"seq": e.seq, **e.to_contract()} for e in events]
