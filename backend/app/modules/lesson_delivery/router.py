import copy
import json
import uuid
from typing import Literal
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import DbSession, get_engine
from app.core.household import get_active_profile
from app.core.identity import CurrentActor, ParentActor, ensure_student_access

from .models import LearningProgress, SchoolRoutine, Timetable
from .routines import refresh_routine, routine_snapshot
from .runtime import RELOAD_TIMEOUT, VOICE, act, refresh_delays, snapshot, start_worker, voice_request

router = APIRouter()


class RoutineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_time: str = Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


class ActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot_id: str
    action: Literal["start", "borrow", "position", "finish", "cancel", "heartbeat", "exit", "rejoin"]
    position: int | None = None


class NarrateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot_id: str
    segment_id: str
    voice: Literal["af_heart", "am_michael"]


def available():
    return voice_request("/catalog")["cards"]


def owned(db, actor, key, lock=False):
    query = select(Timetable).where(Timetable.id == key, Timetable.household_id == actor.household_id)
    if lock:
        query = query.with_for_update()
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "Timetable not found.")
    ensure_student_access(actor, row.student_id)
    if not get_active_profile(db, actor.household_id, row.student_id):
        raise HTTPException(404, "Profile unavailable.")
    return row


@router.get("/catalog/{student_id}")
def catalog(student_id: uuid.UUID, actor: CurrentActor, db: DbSession):
    ensure_student_access(actor, student_id)
    profile = get_active_profile(db, actor.household_id, student_id)
    if not profile:
        raise HTTPException(404, "Profile not found.")
    try:
        cards = [c for c in available() if c["grade"] == profile.grade]
    except (OSError, ValueError):
        raise HTTPException(503, "The local lesson service is unavailable.") from None
    cards.sort(key=lambda c: (c["module"], int(c["id"].split("_")[3][1:])))
    return {
        "cards": cards,
        "subjects": [
            {"id": "math", "status": "available"},
            {"id": "science", "status": "coming_soon"},
            {"id": "english", "status": "coming_soon"},
        ],
    }


@router.put("/routine/{student_id}")
def save_routine(student_id: uuid.UUID, body: RoutineInput, actor: ParentActor, db: DbSession):
    profile = get_active_profile(db, actor.household_id, student_id)
    if not profile:
        raise HTTPException(404, "Profile not found.")
    routine = db.scalar(select(SchoolRoutine).where(SchoolRoutine.student_id == student_id).with_for_update())
    changed = routine is not None and routine.start_time != body.start_time
    if routine is None:
        routine = SchoolRoutine(
            student_id=student_id, household_id=actor.household_id, start_time=body.start_time
        )
        db.add(routine)
    else:
        routine.start_time = body.start_time
    try:
        db.flush()
        row = refresh_routine(db, routine, available, changed=changed, force=True)
        db.flush()
    except IntegrityError:
        raise HTTPException(409, "Start time is being updated. Please try again.") from None
    return {"routine": routine_snapshot(routine), "timetable": snapshot(row) if row else None}


@router.get("/routine/{student_id}")
def get_routine(student_id: uuid.UUID, actor: CurrentActor, db: DbSession):
    ensure_student_access(actor, student_id)
    if not get_active_profile(db, actor.household_id, student_id):
        raise HTTPException(404, "Profile not found.")
    return {"routine": routine_snapshot(db.get(SchoolRoutine, student_id))}


@router.get("/student/{student_id}")
def for_student(student_id: uuid.UUID, actor: CurrentActor, db: DbSession):
    ensure_student_access(actor, student_id)
    if not get_active_profile(db, actor.household_id, student_id):
        raise HTTPException(404, "Profile not found.")
    rows = list(
        db.scalars(
            select(Timetable)
            .where(Timetable.student_id == student_id, Timetable.household_id == actor.household_id)
            .order_by(Timetable.created_at.desc())
            .limit(20)
        )
    )
    for r in rows:
        refresh_delays(db, r)
    return {
        "timetables": [snapshot(r) for r in rows],
        "routine": routine_snapshot(db.get(SchoolRoutine, student_id)),
        "learning_progress": progress.state if (progress := db.get(LearningProgress, student_id)) else None,
    }


@router.post("/{key}/action")
def action(key: uuid.UUID, body: ActionInput, actor: CurrentActor, db: DbSession):
    if actor.role != "student":
        raise HTTPException(
            403, "Class controls belong to the student. Parents can set the daily start time."
        )
    row = owned(db, actor, key, True)
    try:
        result = act(db, row, body.slot_id, body.action, body.position)
        if body.action == "cancel":
            for slot in row.state["slots"]:
                if slot["kind"] == "lesson":
                    try:
                        voice_request("/jobs/" + slot["job_id"] + "/cancel", {})
                    except (OSError, ValueError):
                        pass
        return result
    except (ValueError, StopIteration, OSError) as error:
        raise HTTPException(409, str(error) or "Lesson slot unavailable.") from None


def active_slot(row, slot_id):
    slot = next((s for s in row.state["slots"] if s["id"] == slot_id and s["kind"] == "lesson"), None)
    if row.status != "active" or not slot or slot["status"] != "started":
        raise HTTPException(409, "The scheduled class is not active.")
    return slot


@router.get("/{key}/lesson/{slot_id}")
def lesson(key: uuid.UUID, slot_id: str, actor: CurrentActor, db: DbSession):
    row = owned(db, actor, key)
    slot = active_slot(row, slot_id)
    try:
        prepared = voice_request("/jobs/" + slot["job_id"] + "/lesson")
        return {
            **prepared,
            "position": slot["position"],
            "voice": row.state["voice"],
            "preview_only": row.state["allow_drafts"],
        }
    except (OSError, ValueError):
        raise HTTPException(503, "The prepared lesson service is unavailable.") from None


@router.post("/{key}/narrate")
def narrate(key: uuid.UUID, body: NarrateInput, actor: CurrentActor, db: DbSession):
    if actor.role != "student":
        raise HTTPException(403, "Lesson playback belongs to the student.")
    row = owned(db, actor, key)
    slot = active_slot(row, body.slot_id)
    try:
        voice_request("/jobs/" + slot["job_id"] + "/reserve", {}, RELOAD_TIMEOUT)
        prepared = voice_request("/jobs/" + slot["job_id"] + "/lesson")
        if body.segment_id != prepared["segments"][slot["position"]]["id"]:
            raise HTTPException(409, "Narrate the current lesson part.")
        request = Request(
            VOICE + "/narrate",
            data=json.dumps(
                {"job_id": slot["job_id"], "segment_id": body.segment_id, "voice": body.voice}
            ).encode(),
            headers={"Content-Type": "application/json"},
        )
        stream = urlopen(request, timeout=120)
    except (OSError, ValueError):
        raise HTTPException(503, "The local teacher voice is unavailable.") from None

    def frames():
        completed = False
        try:
            for line in stream:
                with Session(get_engine()) as current_db:
                    current = current_db.get(Timetable, key)
                    if not current or current.status != "active":
                        return
                yield line
                try:
                    completed = completed or json.loads(line).get("type") == "done"
                except ValueError:
                    pass
            if completed:
                with Session(get_engine()) as save_db, save_db.begin():
                    saved = save_db.scalar(select(Timetable).where(Timetable.id == key).with_for_update())
                    if saved and saved.status == "active":
                        state = copy.deepcopy(saved.state)
                        saved_slot = next(s for s in state["slots"] if s["id"] == body.slot_id)
                        if saved_slot["status"] == "started":
                            saved_slot["narrated_positions"] = list(
                                set(saved_slot.get("narrated_positions", []) + [slot["position"]])
                            )
                            saved.state = state
        finally:
            stream.close()

    return StreamingResponse(
        frames(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store"}
    )


def on_mount(_api):
    start_worker()
