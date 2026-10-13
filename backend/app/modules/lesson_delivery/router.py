import copy
import json
import time
import uuid
from datetime import datetime
from typing import Literal
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import DbSession, get_engine
from app.core.household import get_active_profile
from app.core.identity import CurrentActor, ParentActor, ensure_student_access

from .models import Timetable
from .runtime import VOICE, act, snapshot, start_worker, voice_request

router = APIRouter()


class PlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: uuid.UUID
    starts_at: datetime
    concept_ids: list[str] = Field(default_factory=list, max_length=8)
    break_minutes: int = Field(default=5, ge=1, le=60)
    prepare_minutes: int | None = Field(default=None, ge=1, le=120)
    allow_drafts: bool = False

    @field_validator("starts_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("Specify a time zone.")
        return value


class ActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot_id: str
    action: Literal["start", "borrow", "position", "finish", "cancel", "retry", "heartbeat"]
    position: int | None = None


class NarrateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot_id: str
    segment_id: str
    voice: Literal["af_heart", "am_michael"]


def available():
    try:
        return voice_request("/catalog")["cards"]
    except (OSError, ValueError):
        raise HTTPException(503, "The local lesson service is unavailable.") from None


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
    cards = [c for c in available() if c["grade"] == profile.grade]
    cards.sort(key=lambda c: (c["module"], int(c["id"].split("_")[3][1:])))
    return {
        "cards": cards,
        "subjects": [
            {"id": "math", "status": "available"},
            {"id": "science", "status": "coming_soon"},
            {"id": "english", "status": "coming_soon"},
        ],
    }


@router.post("", status_code=201)
def create(body: PlanInput, actor: ParentActor, db: DbSession):
    profile = get_active_profile(db, actor.household_id, body.student_id)
    if not profile:
        raise HTTPException(404, "Profile not found.")
    now = time.time() * 1000
    start = body.starts_at.timestamp() * 1000
    if not now + 3000 <= start <= now + 7 * 86400000:
        raise HTTPException(422, "Choose a start time between three seconds and seven days ahead.")
    cards = [c for c in available() if c["grade"] == profile.grade]
    cards.sort(key=lambda c: (c["module"], int(c["id"].split("_")[3][1:])))
    chosen = body.concept_ids
    if not chosen:
        done = {
            s["concept_id"]
            for r in db.scalars(select(Timetable).where(Timetable.student_id == body.student_id))
            for s in r.state["slots"]
            if s["kind"] == "lesson" and s["status"] == "completed"
        }
        chosen = [c["id"] for c in cards if c["id"] not in done][:1]
    bank = {c["id"]: c for c in cards}
    if not chosen or len(set(chosen)) != len(chosen) or any(c not in bank for c in chosen):
        raise HTTPException(422, "Choose matched Maths lessons for this child’s grade.")
    if not body.allow_drafts and any(not bank[c].get("ready_for_delivery") for c in chosen):
        raise HTTPException(
            422, "These cards need human review. A parent can explicitly allow drafts for local evaluation."
        )
    chosen.sort(key=lambda cid: (bank[cid]["module"], int(cid.split("_")[3][1:])))
    lead = body.prepare_minutes or sum(bank[c].get("recommended_prepare_minutes", 15) for c in chosen)
    slots = []
    at = start
    for i, cid in enumerate(chosen):
        card = bank[cid]
        # Before the new script exists, card-plan metadata supplies a provisional window.
        minutes = card.get("estimated_minutes", 20)
        slots.append(
            {
                "id": str(uuid.uuid4()),
                "kind": "lesson",
                "subject": "math",
                "title": card["title"],
                "concept_id": cid,
                "card_version": card["card_version"],
                "job_id": str(uuid.uuid4()),
                "start_ms": at,
                "end_ms": at + minutes * 60000,
                "prepare_at_ms": at - lead * 60000,
                "status": "planned",
                "position": 0,
                "borrowed_minutes": 0,
                "preparation": {"status": "waiting", "percent": 0, "message": "Waiting for preparation time"},
                "timing": card["timing"],
            }
        )
        at += minutes * 60000
        if i < len(chosen) - 1:
            slots.append(
                {
                    "id": str(uuid.uuid4()),
                    "kind": "break",
                    "title": "Break",
                    "subject": "break",
                    "start_ms": at,
                    "end_ms": at + body.break_minutes * 60000,
                    "status": "planned",
                }
            )
            at += body.break_minutes * 60000
    row = Timetable(
        student_id=body.student_id,
        household_id=actor.household_id,
        state={
            "slots": slots,
            "break_minutes": body.break_minutes,
            "prepare_minutes": lead,
            "allow_drafts": body.allow_drafts,
            "voice": "af_heart",
        },
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        raise HTTPException(409, "This child already has an active timetable.") from None
    return snapshot(row)


@router.get("/student/{student_id}")
def for_student(student_id: uuid.UUID, actor: CurrentActor, db: DbSession):
    ensure_student_access(actor, student_id)
    rows = list(
        db.scalars(
            select(Timetable)
            .where(Timetable.student_id == student_id, Timetable.household_id == actor.household_id)
            .order_by(Timetable.created_at.desc())
            .limit(20)
        )
    )
    return {"timetables": [snapshot(r) for r in rows]}


@router.post("/{key}/action")
def action(key: uuid.UUID, body: ActionInput, actor: CurrentActor, db: DbSession):
    row = owned(db, actor, key, True)
    try:
        if body.action == "retry":
            if actor.role != "parent":
                raise HTTPException(403, "A parent must retry preparation.")
            state = copy.deepcopy(row.state)
            slot = next(s for s in state["slots"] if s["id"] == body.slot_id and s["kind"] == "lesson")
            if row.status != "active" or slot["preparation"]["status"] != "failed":
                raise ValueError("Only failed preparation can be retried.")
            voice_request("/jobs/" + slot["job_id"] + "/retry", {})
            slot["preparation"] = {"status": "waiting", "percent": 0, "message": "Retry scheduled"}
            slot["prepare_at_ms"] = min(slot["prepare_at_ms"], time.time() * 1000)
            row.state = state
            return snapshot(row)
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
    row = owned(db, actor, key)
    slot = active_slot(row, body.slot_id)
    try:
        voice_request("/jobs/" + slot["job_id"] + "/reserve", {})
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
