"""Readiness, profile recreation, and attendance must not invent learning progress."""

import asyncio
import copy
import io
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from app.modules.lesson_delivery import curriculum, router, routines, runtime
from app.modules.lesson_delivery.models import LearningProgress, SchoolRoutine, Timetable

from .conftest import PARENT_PIN

FIRST = "math_g1_m1_l1_embedded_numbers"
SECOND = "math_g1_m1_l2_add_one_more"


@pytest.fixture
def school(parent_client, monkeypatch):
    cards = [
        {
            "id": cid,
            "grade": 1,
            "module": 1,
            "title": "Numbers",
            "card_version": 1,
            "ready_for_delivery": True,
            "recommended_prepare_minutes": 15,
        }
        for cid in (FIRST, SECOND)
    ]
    monkeypatch.setattr(router, "available", lambda: cards)
    monkeypatch.setattr(
        curriculum,
        "module_index",
        lambda *args: [{"module": 1, "expected": 2, "lessons": {1: FIRST, 2: SECOND}}],
    )
    monkeypatch.setattr(routines, "clock_now", lambda: datetime(2026, 10, 19, 3, tzinfo=UTC))
    profile = parent_client.post("/api/profiles", json={"display_name": "Ali", "grade": 1}).json()
    result = parent_client.put(f"/api/lesson_delivery/routine/{profile['id']}", json={"start_time": "09:00"})
    assert result.status_code == 200
    return profile, result.json()["timetable"], cards


def test_same_name_recreation_starts_at_lesson_one(parent_client, school, db):
    old, day, _ = school
    row = db.get(Timetable, uuid.UUID(day["id"]))
    state = copy.deepcopy(row.state)
    state["slots"][0].update(status="completed", narrated_positions=[0], started_at_ms=1)
    row.state, row.status = state, "completed"
    db.flush()
    assert (
        parent_client.post(f"/api/profiles/{old['id']}/unenroll", json={"pin": PARENT_PIN}).status_code == 204
    )
    new = parent_client.post("/api/profiles", json={"display_name": "Ali", "grade": 1}).json()
    assert new["id"] != old["id"]
    assert parent_client.get(f"/api/lesson_delivery/student/{old['id']}").status_code == 404
    assert db.get(LearningProgress, uuid.UUID(old["id"])) is None
    planned = parent_client.put(
        f"/api/lesson_delivery/routine/{new['id']}", json={"start_time": "09:00"}
    ).json()
    assert planned["timetable"]["slots"][0]["concept_id"] == FIRST
    assert planned["timetable"]["slots"][0]["job_id"] != day["slots"][0]["job_id"]
    assert planned["timetable"]["slots"][0]["position"] == 0
    progress = db.get(LearningProgress, uuid.UUID(new["id"])).state
    assert progress["delivered_concept_ids"] == []
    assert progress["unfinished_concept_ids"] == []


def test_two_active_profiles_with_the_same_name_keep_independent_progress(parent_client, school, db):
    _, day, _ = school
    row = db.get(Timetable, uuid.UUID(day["id"]))
    state = copy.deepcopy(row.state)
    state["slots"][0]["status"] = "completed"
    row.state, row.status = state, "completed"
    db.flush()
    other = parent_client.post("/api/profiles", json={"display_name": "Ali", "grade": 1}).json()
    result = parent_client.put(
        f"/api/lesson_delivery/routine/{other['id']}", json={"start_time": "09:00"}
    ).json()
    assert result["timetable"]["slots"][0]["concept_id"] == FIRST


def test_unknown_lesson_length_does_not_invent_attendance():
    assert runtime.attendance_of({"narrated_positions": []}) == (0, False)


def test_finishing_a_later_lesson_does_not_reopen_a_closed_earlier_lesson(parent_client, school, db):
    profile, _, _ = school
    progress = db.get(LearningProgress, uuid.UUID(profile["id"]))
    state = copy.deepcopy(progress.state)
    state["modules"][0]["lessons"][0]["status"] = "unfinished"
    progress.state = state
    db.flush()
    curriculum.mark_delivered(db, progress.student_id, SECOND)
    assert progress.state["next_required"] is None
    assert progress.state["modules"][0]["unfinished_lessons"] == 1


def test_not_joining_a_ready_class_records_absence_and_advances(parent_client, school, db, monkeypatch):
    profile, day, cards = school
    row = db.get(Timetable, uuid.UUID(day["id"]))
    state = copy.deepcopy(row.state)
    state["slots"][0].update(preparation={"status": "ready", "percent": 100}, segment_count=3)
    row.state = state
    db.flush()
    monkeypatch.setattr(routines, "clock_now", lambda: datetime(2026, 10, 20, 3, tzinfo=UTC))
    routine = db.get(SchoolRoutine, uuid.UUID(profile["id"]))
    following = routines.refresh_routine(db, routine, lambda: cards, force=True)
    assert following.state["slots"][0]["concept_id"] == SECOND
    progress = db.get(LearningProgress, routine.student_id).state
    assert progress["next_required"]["lesson"] == 2
    assert progress["unfinished_concept_ids"] == [FIRST]


def test_old_did_not_join_records_count_as_closed_lessons(parent_client, school, db):
    profile, day, cards = school
    row = db.get(Timetable, uuid.UUID(day["id"]))
    state = copy.deepcopy(row.state)
    state["slots"][0].update(status="unfinished", attendance={"status": "absent", "reason": "did_not_join"})
    row.state, row.status = state, "completed"
    db.flush()
    progress = curriculum.synchronize(db, row.household_id, row.student_id, 1, cards)
    assert progress["next_required"]["lesson"] == 2
    assert progress["unfinished_concept_ids"] == [FIRST]


def test_preparation_percentage_alone_never_makes_a_lesson_ready(monkeypatch):
    state = {
        "slots": [
            {
                "kind": "lesson",
                "concept_id": FIRST,
                "job_id": str(uuid.uuid4()),
                "preparation": {"status": "preparing", "percent": 99},
            }
        ]
    }
    monkeypatch.setattr(runtime, "voice_request", lambda *a: {"status": "preparing", "percent": 100})
    assert runtime.refresh_preparation(state, 0)
    assert state["slots"][0]["preparation"]["status"] == "preparing"
    assert state["slots"][0]["preparation"]["percent"] < 100


def test_a_ready_job_for_the_wrong_lesson_is_never_published(monkeypatch):
    state = {
        "slots": [
            {
                "kind": "lesson",
                "concept_id": FIRST,
                "job_id": str(uuid.uuid4()),
                "start_ms": 0,
                "end_ms": 900000,
                "preparation": {"status": "preparing"},
            }
        ]
    }

    def service(path, payload=None):
        if path == "/jobs":
            return {"status": "ready", "percent": 100}
        return {"concept_id": SECOND, "grade": 1, "segments": [{"id": "s1"}], "timing": {"minutes": 15}}

    monkeypatch.setattr(runtime, "voice_request", service)
    with pytest.raises(ValueError, match="identity"):
        runtime.refresh_preparation(state, 0)
    assert state["slots"][0]["preparation"]["status"] != "ready"


def test_plain_text_voice_error_keeps_http_status(monkeypatch):
    def bad_gateway(*args, **kwargs):
        raise HTTPError(
            "http://127.0.0.1:8766/jobs", 502, "Bad Gateway", None, io.BytesIO(b"upstream failed")
        )

    monkeypatch.setattr(runtime, "urlopen", bad_gateway)
    with pytest.raises(ValueError, match="HTTP 502"):
        runtime.voice_request("/jobs")


def test_malformed_catalog_card_is_a_controlled_service_error(parent_client, school, monkeypatch):
    profile, _, _ = school
    monkeypatch.setattr(router, "available", lambda: [{"id": "math", "grade": 1, "module": 1}])
    response = parent_client.get(f"/api/lesson_delivery/catalog/{profile['id']}")
    assert response.status_code == 503


def test_progress_keeps_another_started_module_in_progress(parent_client, school, db):
    profile, _, _ = school
    progress = db.get(LearningProgress, uuid.UUID(profile["id"]))
    state = copy.deepcopy(progress.state)
    state["modules"].append(
        {
            "module": 2,
            "expected_lessons": 1,
            "delivered_lessons": 0,
            "unfinished_lessons": 0,
            "status": "in_progress",
            "lessons": [
                {"lesson": 1, "concept_id": "math_g1_m2_l1_test", "matched": True, "status": "in_progress"}
            ],
        }
    )
    progress.state = state
    db.flush()
    curriculum.mark_delivered(db, progress.student_id, FIRST)
    assert progress.state["modules"][1]["status"] == "in_progress"


def test_narration_reuses_one_connection_but_checks_every_frame(monkeypatch):
    key, household = uuid.uuid4(), uuid.uuid4()
    slot = {
        "id": "slot",
        "kind": "lesson",
        "status": "started",
        "job_id": str(uuid.uuid4()),
        "concept_id": FIRST,
        "position": 0,
    }
    row = SimpleNamespace(status="active", state={"slots": [slot]})
    actor = SimpleNamespace(role="student", household_id=household)
    checks = []
    connections = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execution_options(self, **options):
            assert options["isolation_level"] == "AUTOCOMMIT"
            return self

        def scalar(self, _query):
            checks.append(1)
            return "active" if len(checks) < 3 else "cancelled"

    class Engine:
        def connect(self):
            connection = Connection()
            connections.append(connection)
            return connection

    class Stream:
        closed = False

        def __iter__(self):
            return iter([b'{"type":"audio"}\n'] * 3)

        def close(self):
            self.closed = True

    stream = Stream()
    monkeypatch.setattr(router, "owned", lambda *args: row)
    monkeypatch.setattr(router, "get_engine", lambda: Engine())
    monkeypatch.setattr(router, "urlopen", lambda *args, **kwargs: stream)
    monkeypatch.setattr(
        router, "voice_request", lambda *args, **kwargs: {"concept_id": FIRST, "segments": [{"id": "s1"}]}
    )
    response = router.narrate(
        key, router.NarrateInput(slot_id="slot", segment_id="s1", voice="af_heart"), actor, None
    )

    async def read_frames():
        return [line async for line in response.body_iterator]

    assert len(asyncio.run(read_frames())) == 2
    assert len(connections) == 1 and len(checks) == 3
    assert stream.closed


def test_narration_is_saved_before_done_reaches_child(monkeypatch):
    key, household = uuid.uuid4(), uuid.uuid4()
    slot = {
        "id": "slot",
        "kind": "lesson",
        "status": "started",
        "job_id": str(uuid.uuid4()),
        "concept_id": FIRST,
        "position": 0,
        "narrated_positions": [],
    }
    row = SimpleNamespace(status="active", state={"slots": [slot]})
    actor = SimpleNamespace(role="student", household_id=household)
    saved = False

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execution_options(self, **_):
            return self

        def scalar(self, _query):
            return "active"

    class Engine:
        def connect(self):
            return Connection()

    class SaveSession:
        def __init__(self, _engine):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        @contextmanager
        def begin(self):
            nonlocal saved
            yield self
            saved = True

        def scalar(self, _query):
            return row

    class Stream:
        def __iter__(self):
            return iter([b'{"type":"done"}\n'])

        def close(self):
            pass

    monkeypatch.setattr(router, "owned", lambda *args: row)
    monkeypatch.setattr(router, "get_engine", lambda: Engine())
    monkeypatch.setattr(router, "Session", SaveSession)
    monkeypatch.setattr(router, "urlopen", lambda *args, **kwargs: Stream())
    monkeypatch.setattr(
        router, "voice_request", lambda *args, **kwargs: {"concept_id": FIRST, "segments": [{"id": "s1"}]}
    )
    response = router.narrate(
        key, router.NarrateInput(slot_id="slot", segment_id="s1", voice="af_heart"), actor, None
    )

    async def read_frames():
        async for line in response.body_iterator:
            assert line == b'{"type":"done"}\n'
            assert saved and 0 in row.state["slots"][0]["narrated_positions"]

    asyncio.run(read_frames())


@pytest.mark.parametrize("replace_job", [False, True])
def test_worker_calls_voice_outside_transactions_and_discards_stale_results(monkeypatch, replace_job):
    key, old_job, new_job = uuid.uuid4(), str(uuid.uuid4()), str(uuid.uuid4())
    row = SimpleNamespace(
        id=key,
        status="active",
        state={
            "slots": [
                {
                    "id": "slot",
                    "kind": "lesson",
                    "status": "planned",
                    "job_id": old_job,
                    "concept_id": FIRST,
                    "prepare_at_ms": 0,
                    "start_ms": 0,
                    "end_ms": 900_000,
                    "preparation": {"status": "waiting", "percent": 0},
                }
            ]
        },
    )
    transaction_depth = 0
    voice_calls = []

    class FakeSession:
        def __init__(self, _engine):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        @contextmanager
        def begin(self):
            nonlocal transaction_depth
            transaction_depth += 1
            try:
                yield self
            finally:
                transaction_depth -= 1

        def scalars(self, _query):
            return [key]

        def scalar(self, _query):
            return row

        def get(self, _model, _key):
            return row

    def service(path, *args):
        assert transaction_depth == 0, "voice HTTP must not run while a schedule transaction is open"
        voice_calls.append(path)
        if path == "/catalog":
            return {"cards": []}
        if path == "/jobs":
            if replace_job:
                row.state["slots"][0]["job_id"] = new_job
            return {"status": "ready", "percent": 100}
        return {"concept_id": FIRST, "segments": [{"id": "s1"}], "timing": {"minutes": 15}}

    monkeypatch.setattr(runtime, "Session", FakeSession)
    monkeypatch.setattr(runtime, "get_engine", lambda: None)
    monkeypatch.setattr(runtime, "voice_request", service)
    monkeypatch.setattr(routines, "maintain_routines", lambda *args: None)
    monkeypatch.setattr(runtime, "settle_due", lambda *args: None)
    monkeypatch.setattr(runtime, "expire_disconnected", lambda *args, **kwargs: False)
    monkeypatch.setattr(runtime, "refresh_delays", lambda *args: None)

    runtime.poll_preparation_once()
    assert voice_calls == ["/catalog", "/jobs", f"/jobs/{old_job}/lesson"]
    assert transaction_depth == 0
    if replace_job:
        assert row.state["slots"][0]["job_id"] == new_job
        assert row.state["slots"][0]["preparation"]["status"] == "waiting"
    else:
        assert row.state["slots"][0]["preparation"]["status"] == "ready"


def test_failed_earlier_preparation_does_not_starve_a_later_due_slot(monkeypatch):
    key = uuid.uuid4()
    jobs = [str(uuid.uuid4()), str(uuid.uuid4())]
    row = SimpleNamespace(
        id=key,
        status="active",
        state={
            "slots": [
                {
                    "id": str(index),
                    "kind": "lesson",
                    "status": "planned",
                    "job_id": job,
                    "concept_id": FIRST if index == 0 else SECOND,
                    "prepare_at_ms": 0,
                    "start_ms": 0,
                    "end_ms": 900_000,
                    "preparation": {"status": "waiting", "percent": 0},
                }
                for index, job in enumerate(jobs)
            ]
        },
    )

    class FakeSession:
        def __init__(self, _engine):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        @contextmanager
        def begin(self):
            yield self

        def scalars(self, _query):
            return [key]

        def scalar(self, _query):
            return row

        def get(self, _model, _key):
            return row

    called = []

    def service(path, payload=None):
        if path == "/catalog":
            return {"cards": []}
        called.append(payload["job_id"])
        return {"status": "failed" if payload["job_id"] == jobs[0] else "queued", "percent": 0}

    monkeypatch.setattr(runtime, "Session", FakeSession)
    monkeypatch.setattr(runtime, "get_engine", lambda: None)
    monkeypatch.setattr(runtime, "voice_request", service)
    monkeypatch.setattr(routines, "maintain_routines", lambda *args: None)
    monkeypatch.setattr(runtime, "settle_due", lambda *args: None)
    monkeypatch.setattr(runtime, "expire_disconnected", lambda *args, **kwargs: False)
    monkeypatch.setattr(runtime, "refresh_delays", lambda *args: None)

    runtime.poll_preparation_once()
    assert called == jobs
    assert [s["preparation"]["status"] for s in row.state["slots"]] == ["failed", "queued"]
