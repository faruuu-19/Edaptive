"""Application scheduling state and authenticated, local computation boundary."""

import copy
import json
import os
import threading
import time
import uuid
from datetime import UTC, datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.session_log import append

from .models import Timetable

VOICE = "http://127.0.0.1:8766"
# The teacher voice is unloaded between classes; reserving it may have to load the model again.
RELOAD_TIMEOUT = 60


# A child may leave a live class and come back, but the clock never moves because of it.
CLASS_MINUTES = 20
# A class that is over for good. "unfinished" means it was held but not finished (left early, or
# never joined): the lesson does not come back, its rest is for the recorded lessons library.
CLOSED = {"completed", "unfinished", "cancelled"}
DISCONNECT_MS = 120_000


# Present means staying for at least this share of the lesson (the parts the child has listened to).
ATTENDANCE_PERCENT = 70


def attendance_of(slot):
    """(percent, present) for this attempt. A lesson carried over from yesterday only expects the rest."""
    base = slot.get("attempt_base", 0)
    expected = max(0, slot.get("segment_count", 0) - base)
    heard = max(0, len(set(slot.get("narrated_positions", []))) - base)
    if expected == 0:
        return 0, False
    return min(100, round(heard * 100 / expected)), heard * 100 >= ATTENDANCE_PERCENT * expected


def close_day_if_over(row, state):
    """Once every lesson of the day is closed the timetable is complete; the next day is planned from it."""
    if row.status == "active" and not any(
        s["kind"] == "lesson" and s["status"] not in CLOSED for s in state["slots"]
    ):
        row.status = "completed"


def can_rejoin(slot, now_ms):
    """Leaving never shortens or extends the original class window."""
    return slot["status"] == "exited" and now_ms < slot["end_ms"]


def leave(slot, now_ms, reason):
    slot.update(
        status="exited", exited_at_ms=now_ms, exit_reason=reason, exit_count=slot.get("exit_count", 0) + 1
    )


def voice_request(path, payload=None, timeout=5):
    req = Request(
        VOICE + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as error:
        try:
            body = json.load(error)
            detail = body.get("detail") if isinstance(body, dict) else None
        except (ValueError, UnicodeError):
            detail = None
        if not isinstance(detail, str) or not detail:
            detail = f"Local lesson service returned HTTP {error.code}."
        raise ValueError(detail) from None


def estimate(lesson):
    return lesson["timing"]


def event(db, row, kind, slot, payload=None):
    now = datetime.now(UTC).isoformat()
    session = slot.get("session_id")
    common = {
        "event_id": str(uuid.uuid4()),
        "event_version": 1,
        "occurred_at": now,
        "source": "lesson_delivery",
        "session_id": session,
        "student_id": str(row.student_id),
    }
    if kind in {"start", "rejoin"}:
        append(
            db,
            {
                **common,
                "event_type": "session.started",
                "payload": {
                    "entry": "scheduled",
                    "concept_id": slot["concept_id"],
                    "card_version": slot["card_version"],
                },
            },
        )
    elif kind in {"finish", "cancel", "exit"} and session:
        reason = (
            "completed"
            if kind == "finish"
            else "timeout"
            if slot.get("exit_reason") == "timeout"
            else "exited"
        )
        append(db, {**common, "event_type": "session.ended", "payload": {"reason": reason}})
    append(
        db,
        {
            **common,
            "event_id": str(uuid.uuid4()),
            "event_type": "lesson.delivery_changed",
            "payload": {
                "timetable_id": str(row.id),
                "slot_id": slot["id"],
                "action": kind,
                "concept_id": slot["concept_id"],
                "card_version": slot["card_version"],
                "position": slot.get("position", 0),
                **(payload or {}),
            },
        },
    )


def shift(state, offset, delta):
    for s in state["slots"][offset:]:
        s["start_ms"] += delta
        s["end_ms"] += delta
        if "prepare_at_ms" in s:
            s["prepare_at_ms"] += delta


SCHOOL_ZONE = ZoneInfo("Asia/Karachi")
STEP_MS = 300000  # delays are whole five-minute steps, like the snooze
MAX_DELAY_MS = 240 * 60000  # after this the class is simply not held today and the day-end rules apply
NOT_WAITED_FOR = {"ready", "failed", "cancelled"}


def wall_clock(ms):
    return datetime.fromtimestamp(ms / 1000, SCHOOL_ZONE).strftime("%I:%M %p").lstrip("0").lower()


def delay_for(slot, now_ms):
    """How long to wait for a lesson that is still being prepared, from how fast it has gone so far."""
    percent = slot["preparation"].get("percent") or 0
    elapsed = max(now_ms - slot["prepare_at_ms"], 0)
    remaining = elapsed * (100 - percent) / percent if percent >= 1 else 2 * STEP_MS
    steps = max(1, -(-int(remaining) // STEP_MS))
    return min(steps, 12) * STEP_MS


def delay_unready_classes(state, now_ms):
    """A class whose time has come before its lesson is ready is moved later, not skipped. The delay is
    worked out from the preparation so far; the child and parent are told the new time. This and every later
    slot move together, so breaks are kept. True when something moved."""
    moved = False
    for index, slot in enumerate(state["slots"]):
        if (
            slot["kind"] != "lesson"
            or slot["status"] != "planned"
            or now_ms < slot["start_ms"]
            or slot["preparation"]["status"] in NOT_WAITED_FOR
        ):
            continue
        total = slot.get("delay_minutes", 0) * 60000
        if total >= MAX_DELAY_MS:
            continue
        delta = min(delay_for(slot, now_ms), MAX_DELAY_MS - total)
        first_due = slot.get("delayed_from_ms", slot["start_ms"])
        shift(state, index, delta)
        slot.update(
            delayed_from_ms=first_due,
            delay_minutes=(total + delta) // 60000,
            delay_notice=(
                f"Your Maths class will start at {wall_clock(slot['start_ms'])} instead of "
                f"{wall_clock(first_due)}. Your lesson is still being prepared."
            ),
        )
        moved = True
        break  # later classes were moved along with this one
    return moved


def refresh_delays(db, row, now_ms=None):
    state = copy.deepcopy(row.state)
    if row.status == "active" and delay_unready_classes(state, now_ms or time.time() * 1000):
        row.state = state
        db.flush()
        return True
    return False


def snapshot(row, now=None):
    state = copy.deepcopy(row.state)
    now = now or time.time() * 1000
    for slot in state["slots"]:
        phase = slot["status"]
        if slot["kind"] == "break" and phase != "cancelled":
            phase = (
                "completed" if now >= slot["end_ms"] else "break" if now >= slot["start_ms"] else "waiting"
            )
        if phase == "planned":
            phase = (
                "ringing"
                if slot["kind"] == "lesson"
                and slot.get("preparation", {}).get("status") == "ready"
                and now >= slot["start_ms"]
                else "waiting"
            )
        elif phase == "exited":
            phase = "exited" if can_rejoin(slot, now) else "unfinished"
        slot["class_phase"] = phase
    current = next(
        (s for s in state["slots"] if s["kind"] == "lesson" and s["status"] not in CLOSED),
        None,
    )
    return {
        "id": str(row.id),
        "student_id": str(row.student_id),
        "status": row.status,
        **state,
        "current_slot_id": current["id"] if current and row.status == "active" else None,
        "server_now_ms": now,
    }


def act(db, row, slot_id, action, position=None, *, voice_reserved=False):
    state = copy.deepcopy(row.state)
    if row.status != "active":
        raise ValueError("This timetable has ended.")
    index = next(
        (i for i, s in enumerate(state["slots"]) if s["id"] == slot_id and s["kind"] == "lesson"), None
    )
    if index is None:
        raise ValueError("Unknown lesson slot.")
    slot = state["slots"][index]
    current = next(
        (s for s in state["slots"] if s["kind"] == "lesson" and s["status"] not in CLOSED),
        None,
    )
    if current is not slot:
        raise ValueError("Finish the earlier lesson before starting this one.")
    now = time.time() * 1000
    if action == "borrow":
        if slot["status"] != "planned" or now < slot["start_ms"]:
            raise ValueError("Borrow five minutes when the class alarm rings.")
        if slot.get("borrowed_minutes", 0) > 0:
            raise ValueError("You can snooze a class only once.")
        shift(state, index, 300000)
        slot["borrowed_minutes"] = 5
    elif action == "start":
        if slot["status"] == "started":
            return snapshot(row)
        if slot["status"] != "planned":
            raise ValueError("Rejoin a class you already started; Start is for a new class.")
        if now < slot["start_ms"] or slot["preparation"]["status"] != "ready":
            raise ValueError("Wait for class time and completed preparation.")
        # A class lasts twenty minutes from its first start; rejoining never moves this clock.
        slot["timing"] = {**slot.get("timing", {}), "minutes": CLASS_MINUTES}
        duration_delta = slot["start_ms"] + CLASS_MINUTES * 60000 - slot["end_ms"]
        slot["end_ms"] += duration_delta
        shift(state, index + 1, duration_delta)
        # The actual start time shifts later slots, preserving the planned break.
        if now > slot["start_ms"]:
            shift(state, index, now - slot["start_ms"])
        if not voice_reserved:
            voice_request("/jobs/" + slot["job_id"] + "/reserve", {}, RELOAD_TIMEOUT)
        slot.update(status="started", session_id=str(uuid.uuid4()), started_at_ms=now, last_seen_ms=now)
    elif action == "exit":
        if slot["status"] != "started":
            raise ValueError("You are not in a class right now.")
        leave(slot, now, "child")
    elif action == "rejoin":
        if not can_rejoin(slot, now):
            raise ValueError("This class has finished. Your next Maths lesson is on the next school day.")
        if not voice_reserved:
            voice_request("/jobs/" + slot["job_id"] + "/reserve", {}, RELOAD_TIMEOUT)
        slot.update(status="started", session_id=str(uuid.uuid4()), last_seen_ms=now)
    elif action == "heartbeat":
        if slot["status"] != "started":
            raise ValueError("The lesson is not active.")
        slot["last_seen_ms"] = now
    elif action == "position":
        if slot["status"] != "started":
            raise ValueError("The lesson is not active.")
        if not isinstance(position, int) or not 0 <= position < slot["segment_count"]:
            raise ValueError("Invalid lesson position.")
        # Acknowledgement follows completion of narration or the reflection checkpoint.
        if position > slot.get("position", 0) and slot.get("position", 0) not in slot.get(
            "narrated_positions", []
        ):
            raise ValueError("Listen to the current part before moving ahead.")
        if position > slot.get("position", 0) + 1:
            raise ValueError("Complete the current part before moving ahead.")
        slot["position"] = position
        slot["last_seen_ms"] = now
    elif action == "finish":
        if (
            slot["status"] != "started"
            or slot.get("position", 0) != slot["segment_count"] - 1
            or slot.get("position", 0) not in slot.get("narrated_positions", [])
        ):
            raise ValueError("Complete the lesson before ending it.")
        slot.update(status="completed", ended_at_ms=now)
        # Overruns extend the next break and subsequent slots; they never overlap.
        if now > slot["end_ms"]:
            delta = now - slot["end_ms"]
            slot["end_ms"] = now
            shift(state, index + 1, delta)
    elif action == "cancel":
        for s in state["slots"]:
            if s["status"] not in {"completed", "cancelled"}:
                s["status"] = "cancelled"
        row.status = "cancelled"
    else:
        raise ValueError("Unknown lesson action.")
    if action in {"finish", "cancel", "exit"}:
        try:
            voice_request("/jobs/" + slot["job_id"] + "/release", {})
        except (OSError, ValueError):
            pass
    if action != "heartbeat":
        event(db, row, action, slot)
    if action in {"finish", "exit"}:
        settle_attendance(db, row, slot, state.get("school_date"), now)
    close_day_if_over(row, state)
    row.state = state
    db.flush()
    if action == "start":
        from .curriculum import mark_started

        mark_started(db, row.student_id, slot["concept_id"])
        db.flush()
    if action == "finish":
        from .curriculum import mark_delivered

        mark_delivered(db, row.student_id, slot["concept_id"])
        db.flush()
    return snapshot(row)


def settle_attendance(db, row, slot, school_date, now_ms, *, day_over=False):
    """Log this attempt's attendance once it is final. Returns True when a record was written."""
    if slot.get("attendance"):
        return False
    status = slot["status"]
    if status == "completed":
        percent, present = attendance_of(slot)
        reason = "completed"
    elif status == "exited" and (day_over or not can_rejoin(slot, now_ms)):
        percent, _ = attendance_of(slot)
        present, reason = False, "left_early"
    elif status == "planned" and day_over:
        if slot.get("preparation", {}).get("status") != "ready":
            # No lesson was ready, so the class could not run: nobody was absent. Tried again tomorrow.
            slot["attendance"] = {"status": "not_held"}
            return False
        percent, present, reason = 0, False, "did_not_join"
    else:
        return False
    result = "present" if present else "absent"
    slot["attendance"] = {"status": result, "reason": reason, "attended_percent": percent}
    if status != "completed":
        slot.update(status="unfinished", unfinished_at_ms=now_ms)
    append(
        db,
        {
            "event_id": str(uuid.uuid4()),
            "event_version": 1,
            "occurred_at": datetime.now(UTC).isoformat(),
            "source": "lesson_delivery",
            "session_id": slot.get("session_id"),
            "student_id": str(row.student_id),
            "event_type": "lesson.attendance_recorded",
            "payload": {
                "timetable_id": str(row.id),
                "slot_id": slot["id"],
                "concept_id": slot["concept_id"],
                "card_version": slot["card_version"],
                "school_date": school_date,
                "status": result,
                "reason": reason,
                "attended_percent": percent,
                "lesson_title": slot.get("title", "")[:120],
            },
        },
    )
    return True


def settle_due(db, row, now_ms):
    """Record attendance for classes the child left and can no longer rejoin."""
    state = copy.deepcopy(row.state)
    changed = False
    for slot in state["slots"]:
        if slot["kind"] == "lesson" and slot["status"] == "exited":
            changed = settle_attendance(db, row, slot, state.get("school_date"), now_ms) or changed
    if changed:
        close_day_if_over(row, state)
        row.state = state
        db.flush()
    return changed


def expire_disconnected(db, row, now_ms, release_jobs=None):
    """A started class with no heartbeat for DISCONNECT_MS is treated as left (connection lost)."""
    state = copy.deepcopy(row.state)
    lost = [
        s
        for s in state["slots"]
        if s["kind"] == "lesson"
        and s["status"] == "started"
        and now_ms - s.get("last_seen_ms", s.get("started_at_ms", now_ms)) > DISCONNECT_MS
    ]
    for slot in lost:
        leave(slot, now_ms, "timeout")
        event(db, row, "exit", slot)
        settle_attendance(db, row, slot, state.get("school_date"), now_ms)
        if release_jobs is not None:
            release_jobs.append(slot["job_id"])
        else:
            try:
                voice_request("/jobs/" + slot["job_id"] + "/release", {})
            except (OSError, ValueError):
                pass
    if lost:
        close_day_if_over(row, state)
        row.state = state
        db.flush()
    return bool(lost)


def apply_prepared(state, index, lesson, status):
    slot = state["slots"][index]
    timing = {**estimate(lesson), "minutes": CLASS_MINUTES}
    delta = slot["start_ms"] + CLASS_MINUTES * 60000 - slot["end_ms"]
    slot["end_ms"] += delta
    slot.update(timing=timing, segment_count=len(lesson["segments"]), preparation=status)
    shift(state, index + 1, delta)


def hold_early_jobs(state, now_ms):
    """Preparation follows the timetable. A job that started before its slot's preparation time (for
    example the class was moved later after it began) is cancelled and made again when its time comes.
    Returns the cancelled job ids so the caller can stop them."""
    cancelled = []
    for slot in state["slots"]:
        if (
            slot["kind"] == "lesson"
            and slot["status"] == "planned"
            and slot.get("preparation", {}).get("status") in {"queued", "preparing", "paused"}
            and now_ms < slot["prepare_at_ms"]
        ):
            cancelled.append(slot["job_id"])
            slot.update(
                job_id=str(uuid.uuid4()),
                preparation={
                    "status": "waiting",
                    "percent": 0,
                    "message": "Coming soon · waiting for preparation time",
                },
            )
    return cancelled


def apply_preparation_status(state, index, status, lesson=None):
    """Publish only a checked lesson; this part never talks to the voice service."""
    slot = state["slots"][index]
    slot["preparation"] = {**status, "percent": max(0, min(98, status.get("percent", 0)))}
    if status["status"] == "ready":
        # A missing/invalid finished lesson stays in checking and is retried.
        slot["preparation"] = {**status, "status": "checking", "percent": 98}
        if not isinstance(lesson, dict):
            raise ValueError("The prepared lesson could not be checked.")
        if lesson.get("concept_id") != slot["concept_id"]:
            raise ValueError("Prepared lesson identity does not match the scheduled lesson.")
        if not lesson.get("segments"):
            raise ValueError("The prepared lesson has no playable parts.")
        apply_prepared(state, index, lesson, {**status, "status": "ready", "percent": 100})
    return status["status"] in {"queued", "preparing"}


def refresh_preparation(state, index):
    """Move one planned lesson's preparation forward; True while the voice service is still working."""
    slot = state["slots"][index]
    status = voice_request(
        "/jobs", {"job_id": slot["job_id"], "concept_id": slot["concept_id"], "managed": True}
    )
    if status["status"] == "ready":
        slot["preparation"] = {**status, "status": "checking", "percent": 98}
        lesson = voice_request("/jobs/" + slot["job_id"] + "/lesson")
    else:
        lesson = None
    return apply_preparation_status(state, index, status, lesson)


def started_job(timetable_id, job_id):
    """Read the latest schedule after a remote reservation, without keeping a database lock."""
    with Session(get_engine()) as db:
        row = db.get(Timetable, timetable_id)
        if row and row.status == "active":
            return next(
                (
                    slot
                    for slot in row.state["slots"]
                    if slot.get("job_id") == job_id and slot["status"] == "started"
                ),
                None,
            )
    return None


def poll_catalog_loader():
    """Fetch before any routine/timetable row is locked."""
    try:
        cards = voice_request("/catalog")["cards"]
    except (OSError, ValueError, KeyError) as error:

        def unavailable(source=error):
            raise OSError("Local lesson catalog unavailable.") from source

        return unavailable
    return lambda: cards


def poll_preparation_once():
    """One pass: commit schedule changes before making voice HTTP calls."""
    from .routines import maintain_routines

    cards_loader = poll_catalog_loader()
    with Session(get_engine()) as db, db.begin():
        maintain_routines(db, cards_loader)
    with Session(get_engine()) as db:
        keys = list(db.scalars(select(Timetable.id).where(Timetable.status == "active")))

    for key in keys:
        cancelled, released = [], []
        work = None
        with Session(get_engine()) as db, db.begin():
            row = db.scalar(
                select(Timetable)
                .where(Timetable.id == key, Timetable.status == "active")
                .with_for_update(skip_locked=True)
            )
            if row is None:
                continue
            now_ms = time.time() * 1000
            settle_due(db, row, now_ms)
            disconnected = expire_disconnected(db, row, now_ms, release_jobs=released)
            if row.status == "active" and not disconnected:
                refresh_delays(db, row, now_ms)
                state = copy.deepcopy(row.state)
                cancelled = hold_early_jobs(state, now_ms)
                row.state = state
                active = next((s for s in state["slots"] if s["status"] == "started"), None)
                if active:
                    endpoint = (
                        "/reserve"
                        if now_ms - active.get("last_seen_ms", active["started_at_ms"]) < 90000
                        else "/release"
                    )
                    work = ("reservation", active["job_id"], endpoint)
                else:
                    due = [
                        (s["id"], s["job_id"], s["concept_id"])
                        for s in state["slots"]
                        if s["kind"] == "lesson"
                        and s["status"] == "planned"
                        and now_ms >= s["prepare_at_ms"]
                        and s["preparation"]["status"] != "ready"
                    ]
                    if due:
                        work = ("prepare", due)

        for job_id in cancelled:
            try:
                voice_request("/jobs/" + job_id + "/cancel", {})
            except (OSError, ValueError):
                pass
        for job_id in released:
            if started_job(key, job_id) is None:
                try:
                    voice_request("/jobs/" + job_id + "/release", {})
                except (OSError, ValueError):
                    pass
        if work is None:
            continue
        if work[0] == "reservation":
            _, job_id, endpoint = work
            current = started_job(key, job_id)
            if (
                endpoint == "/release"
                and current
                and time.time() * 1000 - current.get("last_seen_ms", current["started_at_ms"]) < 90000
            ):
                continue
            try:
                voice_request("/jobs/" + job_id + endpoint, {})
                if endpoint == "/reserve" and started_job(key, job_id) is None:
                    voice_request("/jobs/" + job_id + "/release", {})
            except (OSError, ValueError):
                pass
            continue

        for slot_id, job_id, concept_id in work[1]:
            # A prior ready lesson may have shifted this slot's preparation time.
            with Session(get_engine()) as db:
                latest = db.get(Timetable, key)
                due = bool(
                    latest
                    and latest.status == "active"
                    and any(
                        s["id"] == slot_id
                        and s.get("job_id") == job_id
                        and s["status"] == "planned"
                        and s["preparation"]["status"] != "ready"
                        and time.time() * 1000 >= s["prepare_at_ms"]
                        for s in latest.state["slots"]
                    )
                )
            if not due:
                continue
            status, lesson, error = None, None, None
            try:
                status = voice_request("/jobs", {"job_id": job_id, "concept_id": concept_id, "managed": True})
                if status["status"] == "ready":
                    lesson = voice_request("/jobs/" + job_id + "/lesson")
            except (OSError, ValueError, KeyError, TypeError) as caught:
                error = caught
            busy = False
            with Session(get_engine()) as db, db.begin():
                row = db.scalar(
                    select(Timetable)
                    .where(Timetable.id == key, Timetable.status == "active")
                    .with_for_update(skip_locked=True)
                )
                if row is None:
                    continue
                state = copy.deepcopy(row.state)
                index = next(
                    (
                        i
                        for i, s in enumerate(state["slots"])
                        if s["id"] == slot_id and s.get("job_id") == job_id and s["status"] == "planned"
                    ),
                    None,
                )
                if index is None:
                    continue
                slot = state["slots"][index]
                if status is not None:
                    try:
                        busy = apply_preparation_status(state, index, status, lesson)
                    except (ValueError, KeyError, TypeError) as caught:
                        error = caught
                if error is not None:
                    slot["preparation"]["message"] = (
                        "Local preparation service unavailable; retrying automatically."
                    )
                    print(type(error).__name__, "preparation service unavailable", flush=True)
                row.state = state
            if error is not None or busy:
                break


def poll_preparation():
    """Recoverable dispatcher: job ids and progress survive either service restarting."""
    while True:
        try:
            poll_preparation_once()
        except Exception as error:
            print(type(error).__name__, "schedule worker will retry", flush=True)
        time.sleep(1)


def start_worker():
    if os.environ.get("EDAPTIVE_LESSON_WORKER") == "1":
        threading.Thread(target=poll_preparation, daemon=True).start()
