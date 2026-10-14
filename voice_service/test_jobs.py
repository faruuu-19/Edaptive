import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock
from .jobs import PreparationJobs
from .timing import estimate_timing


class StubNarrator:
    def __init__(self):
        self.releases = 0
        self.busy = False

    def warm(self):
        pass

    def release(self):
        if self.busy:
            raise ValueError("Finish the current narration before preparing another class.")
        self.releases += 1


class FakeProcess:
    """Stands in for the preparation worker: replays progress lines, then exits cleanly."""

    def __init__(self, lines, code=0):
        self.stdout = iter(lines)
        self.stderr = type("E", (), {"read": lambda self: ""})()
        self._code = code

    def wait(self):
        return self._code

    def terminate(self):
        pass


class JobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        p = root / "docs/voice-module"
        p.mkdir(parents=True)
        p.joinpath("PAIR_INVENTORY.json").write_text(
            json.dumps(
                {
                    "pairs": [
                        {
                            "concept_id": "math_g2_m1_l1_pairs_to_ten",
                            "plan_passed": True,
                        }
                    ]
                }
            )
        )
        self.root = root
        self.jobs = PreparationJobs(
            root, StubNarrator(), None, root / "store", start_worker=False
        )
        self.request = {
            "job_id": str(uuid.uuid4()),
            "concept_id": "math_g2_m1_l1_pairs_to_ten",
        }

    def tearDown(self):
        self.jobs.close()
        self.tmp.cleanup()

    def test_jobs_are_idempotent_and_survive_restart(self):
        first = self.jobs.submit(self.request)
        self.assertEqual(self.jobs.submit(self.request), first)
        self.jobs.update(first["id"], status="preparing", completed=3, percent=10)
        again = PreparationJobs(
            self.root, StubNarrator(), None, self.root / "store", start_worker=False
        )
        self.assertEqual(again.get(first["id"])["status"], "queued")
        self.assertEqual(again.get(first["id"])["completed"], 3)
        again.close()

    def test_cancelled_job_cannot_publish_stale_progress(self):
        key = self.jobs.submit(self.request)["id"]
        self.jobs.cancel(key)
        self.jobs.update(key, status="ready", percent=100)
        self.assertEqual(self.jobs.get(key)["status"], "cancelled")
        with self.assertRaises(ValueError):
            self.jobs.lesson(key)

    def test_reservation_prevents_conflicting_delivery(self):
        key = self.jobs.submit(self.request)["id"]
        with self.assertRaises(ValueError):
            self.jobs.reserve(key)
        self.jobs.update(key, status="ready")
        self.jobs.reserve(key)
        self.assertGreater(self.jobs.reservation_until, 0)
        self.jobs.release(key)
        self.assertEqual(self.jobs.reservation_until, 0)

    def test_foreground_voice_preempts_future_preparation_without_losing_the_job(self):
        key = self.jobs.submit(self.request)["id"]
        self.jobs.update(key, status="ready")
        future = self.jobs.submit({**self.request, "job_id": str(uuid.uuid4())})["id"]
        self.jobs.update(future, status="preparing", completed=4)
        self.jobs.running = future
        self.jobs.idle.clear()
        jobs = self.jobs

        class Process:
            def terminate(self):
                jobs.running = None
                jobs.idle.set()

        self.jobs.process = Process()
        self.jobs.reserve(key)
        self.assertEqual(self.jobs.get(future)["status"], "paused_for_delivery")
        self.assertEqual(self.jobs.get(future)["completed"], 4)
        self.jobs.process = None
        again = PreparationJobs(
            self.root, StubNarrator(), None, self.root / "store", start_worker=False
        )
        self.assertEqual(again.reservation, key)
        self.assertGreater(again.reservation_until, 0)
        again.close()

    def _prepare_ready(self, name):
        key = self.jobs.submit({**self.request, "job_id": str(uuid.uuid4())})["id"]
        self.jobs.update(key, status="ready")
        return key

    def _runnable(self, key):
        self.jobs.catalog[self.request["concept_id"]].update(
            concept="c.json", assessment="a.json", assessment_id="assess"
        )
        lines = [
            json.dumps({"phase": "generating", "percent": 50, "completed": 42, "total": 84}) + "\n",
            json.dumps(
                {"phase": "validated", "percent": 96, "completed": 84, "total": 84, "script": "/x/s.json"}
            )
            + "\n",
        ]
        return mock.patch(
            "voice_service.jobs.subprocess.Popen", return_value=FakeProcess(lines)
        )

    def test_preparation_that_yielded_to_a_class_resumes_after_release(self):
        self.jobs.loader = lambda path: {"segments": []}
        delivery = self._prepare_ready("class")
        future = self.jobs.submit({**self.request, "job_id": str(uuid.uuid4())})["id"]
        self.jobs.update(future, status="preparing", completed=4, percent=8)
        self.jobs.running = future
        self.jobs.idle.clear()
        jobs = self.jobs

        class Child(FakeProcess):
            def terminate(self):
                jobs.running = None
                jobs.idle.set()

        self.jobs.process = Child([])
        self.jobs.reserve(delivery)
        self.assertEqual(self.jobs.get(future)["status"], "paused_for_delivery")
        self.jobs.process = None
        # While the class is listening, the paused job must stay paused.
        with self._runnable(future):
            self.jobs.run(future)
        self.assertEqual(self.jobs.get(future)["status"], "paused_for_delivery")
        # Once the class releases the model, the next worker pass must finish it.
        self.jobs.release(delivery)
        with self._runnable(future):
            self.jobs.run(future)
        row = self.jobs.get(future)
        self.assertEqual(row["status"], "ready")
        self.assertEqual(row["percent"], 100)

    def test_paused_for_delivery_job_is_still_resumable_after_a_service_restart(self):
        self.jobs.loader = lambda path: {"segments": []}
        future = self.jobs.submit(self.request)["id"]
        self.jobs.update(future, status="paused_for_delivery", completed=4)
        again = PreparationJobs(
            self.root, StubNarrator(), lambda path: {"segments": []}, self.root / "store", start_worker=False
        )
        again.catalog[self.request["concept_id"]].update(
            concept="c.json", assessment="a.json", assessment_id="assess"
        )
        with mock.patch(
            "voice_service.jobs.subprocess.Popen",
            return_value=FakeProcess(
                [json.dumps({"phase": "validated", "percent": 96, "script": "/x/s.json"}) + "\n"]
            ),
        ):
            again.run(future)
        self.assertEqual(again.get(future)["status"], "ready")
        again.close()

    def test_unattended_release_unloads_the_voice_model_once(self):
        narrator = StubNarrator()
        jobs = PreparationJobs(self.root, narrator, None, self.root / "store2", start_worker=False)
        key = jobs.submit(self.request)["id"]
        jobs.update(key, status="ready")
        jobs.reserve(key)
        self.assertEqual(narrator.releases, 0)
        jobs.release(key)
        self.assertEqual(narrator.releases, 1)
        # The scheduler repeats the release every second while the child is away.
        jobs.release(key)
        self.assertEqual(narrator.releases, 1)
        jobs.close()

    def test_release_by_a_lesson_that_is_not_reserved_does_not_unload_the_model(self):
        narrator = StubNarrator()
        jobs = PreparationJobs(self.root, narrator, None, self.root / "store3", start_worker=False)
        key = jobs.submit(self.request)["id"]
        other = jobs.submit({**self.request, "job_id": str(uuid.uuid4())})["id"]
        jobs.update(key, status="ready")
        jobs.reserve(key)
        jobs.release(other)
        self.assertEqual(narrator.releases, 0)
        self.assertEqual(jobs.reservation, key)
        jobs.close()

    def test_release_keeps_the_voice_while_a_sentence_is_still_playing(self):
        narrator = StubNarrator()
        jobs = PreparationJobs(self.root, narrator, None, self.root / "store4", start_worker=False)
        key = jobs.submit(self.request)["id"]
        jobs.update(key, status="ready")
        jobs.reserve(key)
        narrator.busy = True
        self.assertEqual(jobs.release(key), {"released": True})
        self.assertEqual(narrator.releases, 0)
        jobs.close()

    def test_duration_reviews_text_and_has_buffer_and_bounds(self):
        little = [
            {
                "kind": "lecture",
                "utterances": [{"spoken": "Let us count."}],
                "checkpoint": False,
            }
        ]
        self.assertEqual(estimate_timing(little, 2)["minutes"], 15)
        huge = [
            {
                "kind": "lecture",
                "utterances": [{"spoken": "one " * 5000}],
                "checkpoint": False,
            }
        ]
        self.assertEqual(estimate_timing(huge, 2)["minutes"], 35)
        self.assertEqual(estimate_timing(little, 2)["buffer_seconds"], 180)


if __name__ == "__main__":
    unittest.main()
