"""Required sequence and persistent delivery progress, not assessed mastery."""

import copy
import json
import re
from pathlib import Path

from sqlalchemy import select

from .models import LearningProgress, Timetable

ROOT = Path(__file__).resolve().parents[4] / "ciriculam"


def coordinates(cid):
    match = re.match(r"math_g(\d+)_m(\d+)_l(\d+)_", cid)
    return tuple(map(int, match.groups())) if match else None


def walk_cards(value):
    if isinstance(value, dict):
        if "concept_id" in value and "card_version" in value:
            yield value
        else:
            for item in value.values():
                yield from walk_cards(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_cards(item)


def module_index(grade, paired):
    modules = {}
    for path in sorted((ROOT / f"grade{grade}").glob("*_Lessons.json")):
        match = re.search(r"_m(\d+)_", path.name)
        if not match:
            continue
        number = int(match[1])
        body = json.loads(path.read_text())
        cards = list(walk_cards(body))
        lessons = {}
        for card in cards:
            coord = coordinates(card["concept_id"])
            if coord:
                lessons[coord[2]] = card["concept_id"]
        expected = body.get("lessons_expected") if isinstance(body, dict) else None
        if not isinstance(expected, int):
            expected = None
        if not lessons and cards:
            titles = " ".join(r.get("title", "") for c in cards for r in c.get("source_refs", []))
            combined = re.search(r"Lessons\s+1\s+(?:to|[–-])\s+(\d+)", titles, re.I)
            if combined:
                expected = int(combined[1])
        modules[number] = {"module": number, "expected": expected, "lessons": lessons}
    for card in paired:
        coord = coordinates(card["id"])
        if coord and coord[0] == grade:
            module = modules.setdefault(coord[1], {"module": coord[1], "expected": None, "lessons": {}})
            module["lessons"][coord[2]] = card["id"]
    return [
        modules.get(n, {"module": n, "expected": None, "lessons": {}})
        for n in range(1, max(modules, default=1) + 1)
    ]


def synchronize(db, household_id, student_id, grade, paired):
    histories = list(db.scalars(select(Timetable).where(Timetable.student_id == student_id)))
    started = {
        slot["concept_id"]
        for history in histories
        for slot in history.state["slots"]
        if slot["kind"] == "lesson" and slot.get("started_at_ms")
    }
    delivered = {
        s["concept_id"]
        for row in histories
        for s in row.state["slots"]
        if s["kind"] == "lesson" and s["status"] == "completed"
    }
    bank = {c["id"]: c for c in paired}
    modules = []
    next_required = None
    for module in module_index(grade, paired):
        expected = module["expected"]
        last = expected or max(module["lessons"], default=1)
        lessons = []
        for number in range(1, last + 1):
            cid = module["lessons"].get(number)
            complete = bool(cid and cid in delivered)
            lessons.append(
                {
                    "lesson": number,
                    "concept_id": cid,
                    "matched": bool(cid and cid in bank),
                    "status": "delivered" if complete else "in_progress" if cid in started else "pending",
                }
            )
            if next_required is None and not complete:
                next_required = {
                    "module": module["module"],
                    "lesson": number,
                    "concept_id": cid,
                    "matched": bool(cid and cid in bank),
                }
        done = sum(item["status"] == "delivered" for item in lessons)
        complete = expected is not None and done == expected
        if next_required is None and not complete:
            next_required = {
                "module": module["module"],
                "lesson": last + 1,
                "concept_id": None,
                "matched": False,
            }
        modules.append(
            {
                "module": module["module"],
                "expected_lessons": expected,
                "delivered_lessons": done,
                "status": "completed"
                if complete
                else "in_progress"
                if done or any(item["status"] == "in_progress" for item in lessons)
                else "yet_to_learn",
                "coverage_confirmed": expected is not None,
                "lessons": lessons,
            }
        )
    state = {
        "grade": grade,
        "modules": modules,
        "delivered_concept_ids": sorted(delivered),
        "next_required": next_required,
        "mastery_assessed": False,
    }
    row = db.get(LearningProgress, student_id)
    if row is None:
        row = LearningProgress(student_id=student_id, household_id=household_id, state=state)
        db.add(row)
    else:
        row.state = state
    db.flush()
    return state


def mark_delivered(db, student_id, concept_id):
    row = db.get(LearningProgress, student_id)
    if row is None:
        return
    state = copy.deepcopy(row.state)
    state["delivered_concept_ids"] = sorted(set(state["delivered_concept_ids"] + [concept_id]))
    next_required = None
    for module in state["modules"]:
        for lesson in module["lessons"]:
            if lesson["concept_id"] == concept_id:
                lesson["status"] = "delivered"
            if next_required is None and lesson["status"] != "delivered":
                next_required = {
                    "module": module["module"],
                    "lesson": lesson["lesson"],
                    "concept_id": lesson["concept_id"],
                    "matched": lesson["matched"],
                }
        done = sum(item["status"] == "delivered" for item in module["lessons"])
        complete = module["expected_lessons"] is not None and done == module["expected_lessons"]
        module.update(
            delivered_lessons=done,
            status="completed" if complete else "in_progress" if done else "yet_to_learn",
        )
        if next_required is None and not complete:
            next_required = {
                "module": module["module"],
                "lesson": len(module["lessons"]) + 1,
                "concept_id": None,
                "matched": False,
            }
    state["next_required"] = next_required
    row.state = state


def mark_started(db, student_id, concept_id):
    row = db.get(LearningProgress, student_id)
    if row is None:
        return
    state = copy.deepcopy(row.state)
    for module in state["modules"]:
        for lesson in module["lessons"]:
            if lesson["concept_id"] == concept_id and lesson["status"] != "delivered":
                lesson["status"] = "in_progress"
                module["status"] = "in_progress"
    row.state = state
