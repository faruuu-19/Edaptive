"""System-owned daily schedule, strict curriculum order and persistent progress."""

import copy
import os
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.household import get_active_profile

from .curriculum import synchronize
from .models import LearningProgress, SchoolRoutine, Timetable
from .runtime import close_day_if_over, settle_attendance, shift, voice_request

SCHOOL_ZONE = ZoneInfo("Asia/Karachi")
BREAK_MINUTES = 5


def clock_now():
    return datetime.now(UTC)


def next_start(start_time, now, after_date=None):
    local = now.astimezone(SCHOOL_ZONE)
    hour, minute = map(int, start_time.split(":"))
    day = local.date()
    if after_date is not None:
        day = max(day, after_date + timedelta(days=1))
    start = datetime.combine(day, datetime.min.time(), SCHOOL_ZONE).replace(hour=hour, minute=minute)
    if start <= now + timedelta(seconds=3):
        start += timedelta(days=1)
    return start


def routine_snapshot(routine):
    return (
        None
        if routine is None
        else {
            "student_id": str(routine.student_id),
            "start_time": routine.start_time,
            "timezone": "Asia/Karachi",
            "status": routine.status,
            "message": routine.message,
        }
    )


def math_slot(card, at, lead, required=None):
    slot = {
        "id": str(uuid.uuid4()),
        "kind": "unavailable",
        "subject": "math",
        "title": "Maths",
        "start_ms": at,
        "end_ms": at + 20 * 60000,
        "status": "coming_soon",
        "timing": {"minutes": 20, "buffer_seconds": 180, "basis": "provisional", "estimated": True},
    }
    if required:
        slot.update(module=required["module"], lesson=required["lesson"])
    if card:
        slot.update(
            kind="lesson",
            title=card["title"],
            concept_id=card["id"],
            card_version=card["card_version"],
            module=int(card["id"].split("_")[2][1:]),
            lesson=int(card["id"].split("_")[3][1:]),
            job_id=str(uuid.uuid4()),
            prepare_at_ms=at - lead * 60000,
            status="planned",
            position=0,
            borrowed_minutes=0,
            preparation={
                "status": "waiting",
                "percent": 0,
                "message": "Coming soon · waiting for preparation time",
            },
        )
    return slot


def add_break(slots, at):
    slots.append(
        {
            "id": str(uuid.uuid4()),
            "kind": "break",
            "subject": "break",
            "title": "Break",
            "start_ms": at,
            "end_ms": at + BREAK_MINUTES * 60000,
            "status": "planned",
        }
    )
    return at + BREAK_MINUTES * 60000


def append_coming_soon(state):
    if state.get("daily_layout_version") == 2:
        return
    slots = state["slots"]
    # Bring an older not-yet-prepared plan onto the same provisional timing policy.
    for index, slot in enumerate(slots):
        if (
            slot["kind"] == "lesson"
            and slot["status"] == "planned"
            and slot.get("preparation", {}).get("status") != "ready"
        ):
            delta = slot["start_ms"] + 20 * 60000 - slot["end_ms"]
            slot["end_ms"] += delta
            slot["timing"] = {"minutes": 20, "buffer_seconds": 180, "basis": "provisional", "estimated": True}
            shift(state, index + 1, delta)
    at = slots[-1]["end_ms"]
    for subject, title in [("science", "Science"), ("english", "English"), ("physical", "Physical class")]:
        at = add_break(slots, at)
        slots.append(
            {
                "id": str(uuid.uuid4()),
                "kind": "unavailable",
                "subject": subject,
                "title": title,
                "start_ms": at,
                "end_ms": at + 20 * 60000,
                "status": "coming_soon",
                "timing": {"minutes": 20, "buffer_seconds": 180, "basis": "provisional", "estimated": True},
            }
        )
        at += 20 * 60000
    state["daily_layout_version"] = 2


def make_timetable(db, routine, cards, start, required=None):
    allow_drafts = os.environ.get("EDAPTIVE_ALLOW_DRAFT_LESSONS") == "1"
    lead = sum(c.get("recommended_prepare_minutes", 15) for c in cards)
    at = start.timestamp() * 1000
    slots = []
    for i, card in enumerate(cards or [None]):
        if i:
            at = add_break(slots, at)
        slot = math_slot(card, at, lead, required)
        slots.append(slot)
        at = slot["end_ms"]
    state = {
        "slots": slots,
        "break_minutes": BREAK_MINUTES,
        "prepare_minutes": lead,
        "allow_drafts": allow_drafts,
        "voice": "af_heart",
        "school_date": start.date().isoformat(),
        "planning_policy": "strict_curriculum_order",
    }
    append_coming_soon(state)
    row = Timetable(student_id=routine.student_id, household_id=routine.household_id, state=state)
    db.add(row)
    db.flush()
    routine.last_school_date = start.date()
    return row


def refresh_routine(db, routine, cards_loader=None, changed=False, force=False):
    now = clock_now()
    profile = get_active_profile(db, routine.household_id, routine.student_id)
    if not profile:
        return None
    active = db.scalar(
        select(Timetable)
        .where(Timetable.student_id == routine.student_id, Timetable.status == "active")
        .with_for_update()
    )
    if active:
        state = copy.deepcopy(active.state)
        append_coming_soon(state)
        started = any(s["status"] == "started" for s in state["slots"])
        missed = state.get("school_date", "9999") < now.astimezone(SCHOOL_ZONE).date().isoformat()
        now_ms = now.timestamp() * 1000
        if (changed or missed) and not started:
            if missed:
                # The school day is over. A class that was held but not finished is closed for good (its rest
                # is for the recorded lessons library); one that never had a lesson ready is tried again.
                for lesson in state["slots"]:
                    if lesson["kind"] == "lesson":
                        settle_attendance(db, active, lesson, state.get("school_date"), now_ms, day_over=True)
                close_day_if_over(active, state)
            index = next(
                (
                    i
                    for i, s in enumerate(state["slots"])
                    if s["subject"] == "math" and s["kind"] == "lesson" and s["status"] == "planned"
                ),
                None,
            )
            if index is not None:
                at = next_start(routine.start_time, now)
                lesson = state["slots"][index]
                shift(state, index, at.timestamp() * 1000 - lesson["start_ms"])
                lesson.update(borrowed_minutes=0)
                lesson.pop("attendance", None)
                if lesson.get("preparation", {}).get("status") in {"cancelled", "failed"}:
                    # A cancelled or failed job is never reused: prepare again when the new time comes.
                    lesson.update(
                        job_id=str(uuid.uuid4()),
                        preparation={
                            "status": "waiting",
                            "percent": 0,
                            "message": "Coming soon · waiting for preparation time",
                        },
                    )
                state["school_date"] = at.date().isoformat()
                routine.last_school_date = at.date()
        active.state = state
        if active.status != "active":
            active = None  # the day is complete: the next school day is planned below
        elif any(s["kind"] == "lesson" and s["status"] in {"planned", "started"} for s in state["slots"]):
            if force or db.get(LearningProgress, routine.student_id) is None:
                try:
                    synchronize(
                        db,
                        routine.household_id,
                        routine.student_id,
                        profile.grade,
                        (cards_loader or (lambda: voice_request("/catalog")["cards"]))(),
                    )
                except (OSError, ValueError):
                    pass
            routine.status = "scheduled"
            routine.message = "Your daily timetable is planned by the system."
            return active
    if not force and not changed and routine.checked_at and now - routine.checked_at < timedelta(seconds=30):
        return active
    routine.checked_at = now
    try:
        cards = (cards_loader or (lambda: voice_request("/catalog")["cards"]))()
    except (OSError, ValueError):
        routine.status = "waiting_for_service"
        routine.message = "Start time saved. Planning will retry automatically."
        return active
    progress = synchronize(db, routine.household_id, routine.student_id, profile.grade, cards)
    required = progress["next_required"]
    bank = {c["id"]: c for c in cards}
    card = bank.get(required["concept_id"]) if required and required["matched"] else None
    routine.status = "scheduled"
    routine.message = "Your daily timetable is planned by the system."
    if card and not card.get("ready_for_delivery") and os.environ.get("EDAPTIVE_ALLOW_DRAFT_LESSONS") != "1":
        card = None
        routine.status = "awaiting_review"
        routine.message = "The next Maths lesson needs content review before delivery."
    elif card is None:
        routine.status = "content_unavailable"
        routine.message = (
            f"Waiting for Maths Module {required['module']}, Lesson {required['lesson']}. "
            "The system will not skip it."
            if required
            else "All indexed Maths lessons have been delivered. Waiting for the next curriculum stage."
        )
    if active:
        if card:
            state = copy.deepcopy(active.state)
            index = next(i for i, s in enumerate(state["slots"]) if s["subject"] == "math")
            previous = state["slots"][index]
            lead = card.get("recommended_prepare_minutes", 15)
            slot = math_slot(card, previous["start_ms"], lead, required)
            slot["id"] = previous["id"]
            state["slots"][index] = slot
            state.update(
                prepare_minutes=lead, allow_drafts=os.environ.get("EDAPTIVE_ALLOW_DRAFT_LESSONS") == "1"
            )
            active.state = state
        return active
    return make_timetable(
        db,
        routine,
        [card] if card else [],
        next_start(routine.start_time, now, routine.last_school_date),
        required,
    )


def maintain_routines(db):
    for routine in db.scalars(select(SchoolRoutine).with_for_update(skip_locked=True)):
        refresh_routine(db, routine)
