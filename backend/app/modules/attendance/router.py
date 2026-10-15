"""A parent's attendance log, read from the session log. Lesson delivery writes the records."""

import uuid

from fastapi import APIRouter, HTTPException

from app.core.db import DbSession
from app.core.household import get_active_profile
from app.core.identity import ParentActor
from app.session_log.store import read

router = APIRouter()
EVENT = "lesson.attendance_recorded"
# Mirrors ATTENDANCE_PERCENT in lesson delivery; carried in each record's reason, shown here for the UI.
THRESHOLD_PERCENT = 70
MAX_RECORDS = 60


def all_records(db, student_id):
    records, after = [], 0
    while True:
        page = read(db, student_id=student_id, event_types=[EVENT], after_seq=after, limit=500)
        records += page
        if len(page) < 500:
            return records
        after = page[-1].seq


@router.get("/{student_id}")
def get_attendance(student_id: uuid.UUID, actor: ParentActor, db: DbSession):
    if not get_active_profile(db, actor.household_id, student_id):
        raise HTTPException(404, "Profile not found.")
    events = all_records(db, student_id)
    newest_first = sorted(events, key=lambda e: (e.payload["school_date"], e.seq), reverse=True)
    summary = {"present": 0, "absent": 0}
    for event in events:
        summary[event.payload["status"]] += 1
    return {
        "student_id": str(student_id),
        "threshold_percent": THRESHOLD_PERCENT,
        "summary": summary,
        "records": [
            {
                "school_date": e.payload["school_date"],
                "lesson_title": e.payload.get("lesson_title", ""),
                "concept_id": e.payload["concept_id"],
                "status": e.payload["status"],
                "reason": e.payload["reason"],
                "attended_percent": e.payload["attended_percent"],
                "recorded_at": e.occurred_at.isoformat(),
            }
            for e in newest_first[:MAX_RECORDS]
        ],
    }
