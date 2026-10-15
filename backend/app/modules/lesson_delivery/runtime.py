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

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.session_log import append

from .models import Timetable

VOICE = "http://127.0.0.1:8766"
# The teacher voice is unloaded between classes; reserving it may have to load the model again.
RELOAD_TIMEOUT = 60


# A child may leave a live class and come back, but the clock never moves because of it.
MAX_EXITS = 2
DISCONNECT_MS = 120_000


# Present means staying for at least this share of the lesson (the parts the child has listened to).
ATTENDANCE_PERCENT = 70


def attendance_of(slot):
    """(percent, present) for this attempt. A lesson carried over from yesterday only expects the rest."""
    base = slot.get("attempt_base", 0)
    expected = max(0, slot.get("segment_count", 0) - base)
    heard = max(0, len(set(slot.get("narrated_positions", []))) - base)
    if expected == 0:
        return 100, True
    return min(100, round(heard * 100 / expected)), heard * 100 >= ATTENDANCE_PERCENT * expected


def can_rejoin(slot, now_ms):
    """Back in until the class's scheduled end, and at most MAX_EXITS times."""
    return slot["status"] == "exited" and now_ms < slot["end_ms"] and slot.get("exit_count", 0) < MAX_EXITS


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
        detail = json.load(error).get("detail", "Local lesson service unavailable.")
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
            phase = "ringing" if slot["kind"] == "lesson" and now >= slot["start_ms"] else "waiting"
        elif phase == "exited":
            phase = "exited" if can_rejoin(slot, now) else "left_early"
        slot["class_phase"] = phase
    current = next(
        (
            s
            for s in state["slots"]
            if s["kind"] == "lesson" and s["status"] not in {"completed", "cancelled"}
        ),
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


def act(db, row, slot_id, action, position=None):
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
        (
            s
            for s in state["slots"]
            if s["kind"] == "lesson" and s["status"] not in {"completed", "cancelled"}
        ),
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
        if now < slot["start_ms"] or slot["preparation"]["status"] != "ready":
            raise ValueError("Wait for class time and completed preparation.")
        # The actual start time shifts later slots, preserving the planned break.
        if now > slot["start_ms"]:
            shift(state, index, now - slot["start_ms"])
        voice_request("/jobs/" + slot["job_id"] + "/reserve", {}, RELOAD_TIMEOUT)
        slot.update(status="started", session_id=str(uuid.uuid4()), started_at_ms=now, last_seen_ms=now)
    elif action == "exit":
        if slot["status"] != "started":
            raise ValueError("You are not in a class right now.")
        leave(slot, now, "child")
    elif action == "rejoin":
        if not can_rejoin(slot, now):
            raise ValueError(
                "This class has finished. Maths will continue on the next school day from where you stopped."
            )
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
        if not any(s["kind"] == "lesson" and s["status"] == "planned" for s in state["slots"]):
            row.status = "completed"
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
        except OSError:
            pass
    if action != "heartbeat":
        event(db, row, action, slot)
    if action in {"finish", "exit"}:
        settle_attendance(db, row, slot, state.get("school_date"), now)
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
        percent, present = attendance_of(slot)
        reason = "left_after_threshold" if present else "left_early"
    elif status == "planned" and day_over:
        percent, present, reason = 0, False, "did_not_join"
    else:
        return False
    result = "present" if present else "absent"
    slot["attendance"] = {"status": result, "reason": reason, "attended_percent": percent}
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
        row.state = state
        db.flush()
    return changed


def expire_disconnected(db, row, now_ms):
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
        try:
            voice_request("/jobs/" + slot["job_id"] + "/release", {})
        except (OSError, ValueError):
            pass
    if lost:
        row.state = state
        db.flush()
    return bool(lost)


def apply_prepared(state, index, lesson, status):
    slot = state["slots"][index]
    timing = estimate(lesson)
    delta = slot["start_ms"] + timing["minutes"] * 60000 - slot["end_ms"]
    slot["end_ms"] += delta
    slot.update(timing=timing, segment_count=len(lesson["segments"]), preparation=status)
    shift(state, index + 1, delta)


def refresh_preparation(state, index):
    """Move one planned lesson's preparation forward; True while the voice service is still working."""
    slot = state["slots"][index]
    status = voice_request("/jobs", {"job_id": slot["job_id"], "concept_id": slot["concept_id"]})
    slot["preparation"] = status
    if status["status"] == "ready":
        # Fetch the finished lesson before offering Join class. A failure leaves "checking" and is retried.
        slot["preparation"] = {**status, "status": "checking", "percent": 98}
        lesson = voice_request("/jobs/" + slot["job_id"] + "/lesson")
        apply_prepared(state, index, lesson, {**status, "status": "ready", "percent": 100})
    return status["status"] in {"queued", "preparing"}


def poll_preparation():
    """Recoverable dispatcher: job ids and progress survive either service restarting."""
    while True:
        try:
            with Session(get_engine()) as db, db.begin():
                from .routines import maintain_routines

                maintain_routines(db)
                rows = list(
                    db.scalars(
                        select(Timetable)
                        .where(Timetable.status == "active")
                        .with_for_update(skip_locked=True)
                    )
                )
                for row in rows:
                    settle_due(db, row, time.time() * 1000)
                    if expire_disconnected(db, row, time.time() * 1000):
                        continue
                    state = copy.deepcopy(row.state)
                    # Prioritise current delivery over loading another large model.
                    active = next((s for s in state["slots"] if s["status"] == "started"), None)
                    if active:
                        try:
                            endpoint = (
                                "/reserve"
                                if time.time() * 1000 - active.get("last_seen_ms", active["started_at_ms"])
                                < 90000
                                else "/release"
                            )
                            voice_request("/jobs/" + active["job_id"] + endpoint, {})
                        except (OSError, ValueError):
                            pass
                        continue
                    for index, slot in enumerate(state["slots"]):
                        if (
                            slot["kind"] != "lesson"
                            or slot["status"] != "planned"
                            or time.time() * 1000 < slot["prepare_at_ms"]
                        ):
                            continue
                        if slot["preparation"]["status"] in {"ready", "failed"}:
                            continue
                        try:
                            if refresh_preparation(state, index):
                                break
                        except (OSError, ValueError) as error:
                            slot["preparation"]["message"] = (
                                "Local preparation service unavailable; retrying automatically."
                            )
                            print(type(error).__name__, "preparation service unavailable", flush=True)
                            break
                    row.state = state
        except Exception as error:
            print(type(error).__name__, "schedule worker will retry", flush=True)
        time.sleep(1)


def start_worker():
    if os.environ.get("EDAPTIVE_LESSON_WORKER") == "1":
        threading.Thread(target=poll_preparation, daemon=True).start()
