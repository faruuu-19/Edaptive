import json
import tempfile
import unittest
import uuid
from pathlib import Path
from .jobs import PreparationJobs
from .timing import estimate_timing


class StubNarrator:
    def warm(self):
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
