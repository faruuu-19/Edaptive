import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.contracts import get_contracts
from app.session_log.models import Event


def append(db: Session, event: dict[str, Any]) -> int:
    """Validate against the contracts and append. Re-sending the same event_id is a no-op,
    so callers can safely retry. Returns the event's position (seq) in the log."""
    get_contracts().validate_event(event)
    stmt = (
        insert(Event)
        .values(
            event_id=uuid.UUID(event["event_id"]),
            event_type=event["event_type"],
            event_version=event["event_version"],
            occurred_at=datetime.fromisoformat(event["occurred_at"]),
            source=event["source"],
            session_id=event["session_id"],
            student_id=event["student_id"],
            payload=event["payload"],
        )
        .on_conflict_do_nothing(index_elements=["event_id"])
        .returning(Event.seq)
    )
    seq = db.execute(stmt).scalar_one_or_none()
    if seq is None:
        seq = db.execute(select(Event.seq).where(Event.event_id == uuid.UUID(event["event_id"]))).scalar_one()
    return seq


def read(
    db: Session,
    *,
    session_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
    event_types: list[str] | None = None,
    after_seq: int = 0,
    limit: int = 500,
) -> list[Event]:
    """Events in log order. Projections (mastery, progress, replay) page through with after_seq."""
    stmt = select(Event).where(Event.seq > after_seq).order_by(Event.seq).limit(limit)
    if session_id:
        stmt = stmt.where(Event.session_id == session_id)
    if student_id:
        stmt = stmt.where(Event.student_id == student_id)
    if event_types:
        stmt = stmt.where(Event.event_type.in_(event_types))
    return list(db.scalars(stmt))
