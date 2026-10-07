import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Query

from app.core.contracts import ContractError
from app.core.db import DbSession
from app.session_log import store

router = APIRouter(prefix="/api/events", tags=["session-log"])


@router.post("", status_code=201)
def append_event(
    db: DbSession,
    event: Annotated[dict[str, Any], Body(description="EventEnvelope (contracts/events)")],
) -> dict[str, int]:
    try:
        return {"seq": store.append(db, event)}
    except ContractError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from None


@router.get("")
def list_events(
    db: DbSession,
    session_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
    event_type: Annotated[list[str] | None, Query()] = None,
    after_seq: int = 0,
    limit: Annotated[int, Query(le=1000)] = 500,
) -> list[dict[str, Any]]:
    events = store.read(
        db,
        session_id=session_id,
        student_id=student_id,
        event_types=event_type,
        after_seq=after_seq,
        limit=limit,
    )
    return [{"seq": e.seq, **e.to_contract()} for e in events]
