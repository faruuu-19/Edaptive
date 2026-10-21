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
        self.catalog = [{"concept_id": "math_g2_m1_l1_pairs_to_ten", "plan_passed": True}]
        self.jobs = PreparationJobs(
            root, StubNarrator(), None, root / "store", start_worker=False, catalog=self.catalog
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
            self.root, StubNarrator(), None, self.root / "store", start_worker=False, catalog=self.catalog
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
            self.root, StubNarrator(), None, self.root / "store", start_worker=False, catalog=self.catalog
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
            self.root, StubNarrator(), lambda path: {"segments": []}, self.root / "store", start_worker=False, catalog=self.catalog
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
        jobs = PreparationJobs(self.root, narrator, None, self.root / "store2", start_worker=False, catalog=self.catalog)
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
        jobs = PreparationJobs(self.root, narrator, None, self.root / "store3", start_worker=False, catalog=self.catalog)
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
        jobs = PreparationJobs(self.root, narrator, None, self.root / "store4", start_worker=False, catalog=self.catalog)
        key = jobs.submit(self.request)["id"]
        jobs.update(key, status="ready")
        jobs.reserve(key)
        narrator.busy = True
        self.assertEqual(jobs.release(key), {"released": True})
        self.assertEqual(narrator.releases, 0)
        jobs.close()

    def test_incomplete_job_cannot_claim_one_hundred_percent(self):
        key = self.jobs.submit(self.request)["id"]
        for state in ("queued", "preparing", "paused", "failed"):
            self.jobs.update(key, status=state, percent=100)
            self.assertLess(self.jobs.public(key)["percent"], 100)
        self.jobs.update(key, status="ready", percent=100)
        self.assertEqual(self.jobs.public(key)["percent"], 100)

    def test_failed_job_only_retries_after_a_revision_change(self):
        key = self.jobs.submit(self.request)["id"]
        self.jobs.update(key, status="failed", message="Script checks flagged a factual issue")
        self.assertEqual(self.jobs.submit(self.request)["status"], "failed")
        self.jobs.generator_revision += "-corrected"
        self.assertEqual(self.jobs.submit(self.request)["status"], "queued")

    def test_final_script_validation_still_blocks_unsafe_content(self):
        self.jobs.loader = mock.Mock(side_effect=ValueError("Script checks flagged a factual issue"))
        key = self.jobs.submit(self.request)["id"]
        with self._runnable(key):
            self.jobs.run(key)
        self.assertEqual(self.jobs.get(key)["status"], "failed")
        self.assertEqual(self.jobs.get(key)["failure_kind"], "validation")
        self.assertLess(self.jobs.public(key)["percent"], 100)
        with self.assertRaises(ValueError):
            self.jobs.lesson(key)
        self.assertEqual(self.jobs.submit(self.request)["status"], "failed")

    def test_voice_memory_failure_resumes_validated_script_without_regenerating(self):
        self.jobs.loader = mock.Mock(return_value={"segments": []})
        self.jobs.narrator.warm = mock.Mock(side_effect=[RuntimeError("Not enough memory"), None, None])
        key = self.jobs.submit(self.request)["id"]
        with self._runnable(key):
            self.jobs.run(key)
        saved = self.jobs.get(key)
        self.assertEqual(saved["status"], "paused")
        self.assertEqual(saved["script"], "/x/s.json")
        self.assertLess(self.jobs.public(key)["percent"], 100)
        with mock.patch("voice_service.jobs.subprocess.Popen") as process:
            self.jobs.run(key)
        process.assert_not_called()
        self.assertEqual(self.jobs.get(key)["status"], "ready")

    def test_deleted_schedule_expires_work_and_checkpoint_can_resume(self):
        from .jobs import SCHEDULE_LEASE_SECONDS
        request = {**self.request, "managed": True}
        key = self.jobs.submit(request)["id"]
        saved = self.jobs.get(key)
        now = saved["last_requested_at"] + SCHEDULE_LEASE_SECONDS + 1
        with mock.patch("voice_service.jobs.time.time", return_value=now):
            self.assertTrue(self.jobs.expire_schedule(key))
            self.assertEqual(self.jobs.get(key)["status"], "cancelled")
            self.assertEqual(self.jobs.submit(request)["status"], "queued")
            self.assertFalse(self.jobs.expire_schedule(key))

    def test_manual_demo_and_ready_jobs_do_not_expire(self):
        key = self.jobs.submit(self.request)["id"]
        self.jobs.update(key, last_requested_at=0)
        self.assertFalse(self.jobs.expire_schedule(key))
        self.jobs.update(key, managed=True, status="ready")
        self.assertFalse(self.jobs.expire_schedule(key))

    def test_missing_ready_artifact_does_not_break_catalog(self):
        key = self.jobs.submit(self.request)["id"]
        cid = self.request["concept_id"]
        self.jobs.update(key, status="ready", script=str(self.root / "missing.json"))
        self.jobs.catalog[cid]["plan_segments"] = 72
        self.jobs._card_cache = [{"id": cid, "title": "Pairs to ten"}]
        cards = self.jobs.list_cards()
        self.assertEqual(cards[0]["title"], "Pairs to ten")
        cards[0]["title"] = "mutated"
        self.assertEqual(self.jobs.list_cards()[0]["title"], "Pairs to ten")

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
