import base64
import math
import shutil
import struct
import tempfile
import threading
import unittest
from pathlib import Path

from voice_service import lecture
from voice_service.lecture import CompilingNarrator, LectureStore, plan_gestures, speech_bounds

RATE = 24000


def tone(ms, level=9000):
    n = int(RATE * ms / 1000)
    return b"".join(struct.pack("<h", int(level * math.sin(i / 7))) for i in range(n))


def quiet(ms):
    return b"\x00\x00" * int(RATE * ms / 1000)


def sentence_audio(speech_ms=500, lead_ms=200, tail_ms=300):
    return quiet(lead_ms) + tone(speech_ms) + quiet(tail_ms)


def segment(sentences=("Hello there!", "Can you see the pattern?"), segment_id="s1", kind="hook"):
    return {
        "id": segment_id, "kind": kind,
        "utterances": [{"caption": text, "spoken": text.lower()} for text in sentences],
    }


class FakeNarrator:
    """Stands in for the voice model: one audio frame per sentence, or chunks, or a failure, and counts its calls."""

    def __init__(self, chunks=1, fail=False):
        self.lock = threading.Lock()
        self.calls = 0
        self.warmed = 0
        self.chunks, self.fail = chunks, fail

    def warm(self):
        self.warmed += 1

    def frames(self, seg, voice):
        self.calls += 1
        yield {"type": "start", "segment_id": seg["id"]}
        for index, utterance in enumerate(seg["utterances"]):
            for part in range(self.chunks):
                audio = sentence_audio(speech_ms=400 + 100 * index) if self.chunks == 1 else tone(300) + quiet(100)
                yield {"type": "audio", "utterance": index, "caption": utterance["caption"], "sample_rate": RATE,
                       "pcm_s16le": base64.b64encode(audio).decode(), "ready_after_s": 0.1}
            if self.fail and index == 0:
                yield {"type": "error", "detail": "Narration stopped. Please retry."}
                return
        yield {"type": "done", "segment_id": seg["id"]}


def fake_planner(parts):
    """A plan we can read back: one gesture at the start of each sentence's speech."""
    return [[{"atMs": s["startMs"], "name": "index", "seconds": 2.0, "mirror": i % 2 == 0} for i, s in enumerate(p["sentences"])]
            for p in parts]


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.store = LectureStore(self.dir, "fake-engine")


class SpeechBoundsTests(unittest.TestCase):
    def test_finds_speech_inside_the_padding(self):
        start, end = speech_bounds(sentence_audio(500, 200, 300), RATE)
        self.assertAlmostEqual(start, 200, delta=15)
        self.assertAlmostEqual(end, 700, delta=15)

    def test_all_silence_is_treated_as_one_span(self):
        self.assertEqual(speech_bounds(quiet(500), RATE), (0.0, 500.0))


class StoreTests(Base):
    def audio(self, seg=None):
        return [(RATE, sentence_audio(500, 200, 300)), (RATE, sentence_audio(600, 100, 400))]

    def test_round_trip_serves_the_part_with_its_timeline(self):
        seg = segment()
        self.store.save(seg, "af_heart", self.audio(), fake_planner)
        frames = self.store.frames(seg, "af_heart")
        self.assertEqual([f["type"] for f in frames], ["start", "lecture", "audio", "audio", "done"])
        plan = frames[1]
        self.assertEqual(plan["gap_ms"], 1000)
        self.assertEqual(plan["kind"], "hook")
        self.assertEqual([s["utterance"] for s in plan["sentences"]], [0, 1])
        self.assertAlmostEqual(plan["sentences"][0]["speech_start_ms"], 200, delta=15)
        # audio comes back byte for byte
        self.assertEqual(base64.b64decode(frames[2]["pcm_s16le"]), self.audio()[0][1])
        self.assertEqual(frames[2]["caption"], "Hello there!")

    def test_gestures_are_on_one_clock_with_the_gap(self):
        seg = segment()
        self.store.save(seg, "af_heart", self.audio(), fake_planner)
        gestures = self.store.frames(seg, "af_heart")[1]["gestures"]
        first_ms = len(self.audio()[0][1]) / 2 / RATE * 1000
        # sentence 2 starts after sentence 1's whole audio, then the 1 s gap, then her own lead-in silence
        self.assertAlmostEqual(gestures[1]["at_ms"], first_ms + 1000 + 100, delta=15)

    def test_editing_the_script_never_plays_old_audio(self):
        seg = segment()
        self.store.save(seg, "af_heart", self.audio(), fake_planner)
        edited = segment(("Hello there!", "Can you see it?"))
        self.assertIsNone(self.store.frames(edited, "af_heart"))
        self.assertIsNotNone(self.store.frames(seg, "af_heart"))

    def test_another_voice_or_engine_is_a_different_part(self):
        seg = segment()
        self.store.save(seg, "af_heart", self.audio(), fake_planner)
        self.assertIsNone(self.store.frames(seg, "am_michael"))
        self.assertIsNone(LectureStore(self.dir, "other-engine").frames(seg, "af_heart"))

    def test_damaged_files_are_ignored_not_played(self):
        seg = segment()
        meta, pcm = self.store._paths(seg, "af_heart")
        self.store.save(seg, "af_heart", self.audio(), fake_planner)
        original = pcm.read_bytes()
        pcm.write_bytes(original[:-10])                    # truncated
        self.assertIsNone(self.store.frames(seg, "af_heart"))
        pcm.write_bytes(b"\x01" + original[1:])            # same size, one byte changed
        self.assertIsNone(self.store.frames(seg, "af_heart"))
        pcm.write_bytes(original)
        self.assertIsNotNone(self.store.frames(seg, "af_heart"))
        meta.write_text("{not json", encoding="utf-8")     # unreadable timeline
        self.assertIsNone(self.store.frames(seg, "af_heart"))

    def test_changing_the_gesture_rules_recompiles_instead_of_replaying_old_gestures(self):
        from unittest import mock
        seg = segment()
        self.store.save(seg, "af_heart", self.audio(), fake_planner)
        self.assertIsNotNone(self.store.frames(seg, "af_heart"))
        with mock.patch.object(lecture, "rules_fingerprint", return_value="edited-rules"):
            self.assertIsNone(self.store.frames(seg, "af_heart"))  # planned by the old rules: not served

    def test_recompiling_a_part_removes_its_superseded_files_and_only_those(self):
        from unittest import mock
        seg, neighbour, lookalike = segment(), segment(segment_id="s1-extra"), segment(segment_id="s10")
        for each in (seg, neighbour, lookalike):
            self.store.save(each, "af_heart", self.audio(), fake_planner)
        before = sorted(p.name for p in (Path(self.dir) / "fake-engine" / "af_heart").iterdir())
        self.assertEqual(len(before), 6)
        with mock.patch.object(lecture, "rules_fingerprint", return_value="edited-rules"):
            self.store.save(seg, "af_heart", self.audio(), fake_planner)  # s1 recompiled under new rules
            after = sorted(p.name for p in (Path(self.dir) / "fake-engine" / "af_heart").iterdir())
            self.assertEqual(len([n for n in after if n.startswith("s1-") and not n.startswith("s1-extra")]), 2)  # one json, one pcm
            self.assertIsNotNone(self.store.frames(seg, "af_heart"))
        # the neighbour parts (whose names start like s1) still have their original files
        self.assertEqual(len(after), 6)
        self.assertTrue(all(n in after for n in before if n.startswith(("s1-extra", "s10"))))
        self.assertTrue(all(n not in after for n in before if n.startswith("s1-") and not n.startswith("s1-extra")))

    def test_a_timeline_whose_sentence_text_was_tampered_with_is_ignored(self):
        seg = segment()
        self.store.save(seg, "af_heart", self.audio(), fake_planner)
        meta_path, _ = self.store._paths(seg, "af_heart")
        text = meta_path.read_text(encoding="utf-8")
        import json as _json
        meta = _json.loads(text)
        meta["sentences"][0]["spoken_sha256"] = "0" * 64  # the key still matches; the sentence no longer does
        meta_path.write_text(_json.dumps(meta), encoding="utf-8")
        self.assertIsNone(self.store.frames(seg, "af_heart"))

    def test_nonsense_gestures_on_disk_are_rejected(self):
        seg = segment()
        self.store.save(seg, "af_heart", self.audio(), fake_planner)
        meta_path, _ = self.store._paths(seg, "af_heart")
        text = meta_path.read_text(encoding="utf-8").replace('"seconds": 2.0', '"seconds": 999')
        meta_path.write_text(text, encoding="utf-8")
        self.assertIsNone(self.store.frames(seg, "af_heart"))

    def test_no_planner_still_compiles_the_audio(self):
        seg = segment()
        self.store.save(seg, "af_heart", self.audio(), lambda parts: None)
        frames = self.store.frames(seg, "af_heart")
        self.assertIsNone(frames[1]["gestures"])  # the browser then plans live
        self.assertEqual(len(frames), 5)

    def test_ids_with_dots_and_odd_characters_are_safe_file_names(self):
        for part_id in ("a.b.c", "../../escape", "x y/z"):
            seg = segment(segment_id=part_id)
            self.store.save(seg, "af_heart", self.audio(), fake_planner)
            self.assertIsNotNone(self.store.frames(seg, "af_heart"), part_id)
        inside = [p for p in Path(self.dir).rglob("*") if p.is_file()]
        self.assertTrue(all(Path(self.dir) in p.parents for p in inside))

    def test_the_store_keeps_to_its_size_and_drops_the_oldest(self):
        import os
        parts = [segment(segment_id=f"p{i}") for i in range(3)]
        for i, seg in enumerate(parts):
            self.store.save(seg, "af_heart", self.audio(), fake_planner)
            meta, pcm = self.store._paths(seg, "af_heart")
            for path in (meta, pcm):
                os.utime(path, (1000 + i, 1000 + i))
        size_one = sum(p.stat().st_size for p in Path(self.dir).rglob("*") if p.is_file()) // 3
        self.store.prune(size_one * 2 + 10)
        self.assertIsNone(self.store.frames(parts[0], "af_heart"))  # oldest gone
        self.assertIsNotNone(self.store.frames(parts[2], "af_heart"))


class CompilingNarratorTests(Base):
    def make(self, **kw):
        inner = FakeNarrator(**kw)
        return inner, CompilingNarrator(inner, self.store, fake_planner)

    def test_first_play_is_live_and_is_saved_for_next_time(self):
        inner, narrator = self.make()
        seg = segment()
        live = list(narrator.frames(seg, "af_heart"))
        self.assertEqual([f["type"] for f in live], ["start", "audio", "audio", "done"])  # exactly what the voice said
        self.assertEqual(inner.calls, 1)
        again = list(narrator.frames(seg, "af_heart"))
        self.assertEqual(inner.calls, 1)  # not spoken again
        self.assertEqual([f["type"] for f in again], ["start", "lecture", "audio", "audio", "done"])

    def test_a_part_the_child_did_not_finish_is_not_saved(self):
        inner, narrator = self.make()
        seg = segment()
        stream = narrator.frames(seg, "af_heart")
        next(stream), next(stream)
        stream.close()  # the child pressed replay or left
        self.assertFalse(self.store.has(seg, "af_heart"))

    def test_a_failed_narration_is_not_saved(self):
        inner, narrator = self.make(fail=True)
        list(narrator.frames(segment(), "af_heart"))
        self.assertFalse(self.store.has(segment(), "af_heart"))

    def test_chunks_of_one_sentence_become_one_sentence(self):
        inner, narrator = self.make(chunks=2)
        seg = segment()
        list(narrator.frames(seg, "af_heart"))
        frames = narrator.frames(seg, "af_heart")
        audio = [f for f in frames if f["type"] == "audio"]
        self.assertEqual([f["utterance"] for f in audio], [0, 1])
        self.assertEqual(len(base64.b64decode(audio[0]["pcm_s16le"])), 2 * len(tone(300) + quiet(100)))

    def test_everything_else_belongs_to_the_real_narrator(self):
        inner, narrator = self.make()
        self.assertIs(narrator.lock, inner.lock)
        narrator.warm()
        self.assertEqual(inner.warmed, 1)

    def test_prerender_compiles_every_part_for_every_voice_and_skips_done_ones(self):
        inner, narrator = self.make()
        lesson = {"segments": [segment(segment_id="a"), segment(segment_id="b")]}
        seen = []
        self.assertTrue(narrator.prerender_lesson(lesson, ["af_heart", "am_michael"], progress=lambda d, t: seen.append((d, t))))
        self.assertEqual(inner.calls, 4)
        self.assertEqual(seen[-1], (4, 4))
        for seg in lesson["segments"]:
            for voice in ("af_heart", "am_michael"):
                self.assertTrue(self.store.has(seg, voice))
        self.assertTrue(narrator.prerender_lesson(lesson, ["af_heart", "am_michael"]))
        self.assertEqual(inner.calls, 4)  # nothing left to do
        self.assertTrue(inner.lock.acquire(blocking=False))  # the lock is free again for a class

    def test_prerender_stops_when_a_class_starts_and_keeps_what_it_finished(self):
        inner, narrator = self.make()
        lesson = {"segments": [segment(segment_id="a"), segment(segment_id="b"), segment(segment_id="c")]}
        state = {"stop": False}
        narrator.render_original = narrator.render

        def progress(done, total):
            state["stop"] = done >= 1

        self.assertFalse(narrator.prerender_lesson(lesson, ["af_heart"], should_stop=lambda: state["stop"], progress=progress))
        self.assertTrue(self.store.has(lesson["segments"][0], "af_heart"))
        self.assertFalse(self.store.has(lesson["segments"][1], "af_heart"))

    def test_prerender_stops_between_sentences_and_saves_nothing_partial(self):
        inner, narrator = self.make()
        seg = segment()
        counter = {"n": 0}

        def stop_after_two_frames():
            counter["n"] += 1
            return counter["n"] > 2

        self.assertFalse(narrator.render(seg, "af_heart", stop_after_two_frames))
        self.assertFalse(self.store.has(seg, "af_heart"))

    def test_prerender_does_not_wait_on_a_busy_teacher(self):
        inner, narrator = self.make()
        inner.lock.acquire()
        original = inner.lock
        timed = []

        class Impatient:
            def acquire(self, timeout=None):
                timed.append(timeout)
                return False

            def release(self):
                pass

        inner.lock = Impatient()
        self.assertFalse(narrator.prerender_lesson({"segments": [segment()]}, ["af_heart"]))
        self.assertEqual(inner.calls, 0)
        self.assertEqual(timed, [2])
        original.release()


class RecordingJobTests(unittest.TestCase):
    """The job runner compiles a lecture right after a lesson becomes ready, without ever putting that lesson at risk."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / "docs/voice-module").mkdir(parents=True)
        self.catalog = [{"concept_id": "c1", "plan_passed": True, "concept": "c.json", "assessment": "a.json", "assessment_id": "assess"}]
        self.lesson = {"segments": [segment(segment_id="a"), segment(segment_id="b")]}
        self.root = root
        self.made = []

    def jobs(self, prerender):
        from voice_service.jobs import PreparationJobs
        from voice_service.test_jobs import StubNarrator
        jobs = PreparationJobs(self.root, StubNarrator(), lambda path: self.lesson, self.root / "store",
                               start_worker=False, catalog=self.catalog, prerender=prerender)
        self.made.append(jobs)
        self.addCleanup(jobs.close)
        return jobs

    def process(self):
        import json as j
        from unittest import mock
        from voice_service.test_jobs import FakeProcess
        lines = [j.dumps({"phase": "validated", "percent": 96, "completed": 2, "total": 2, "script": "/x/s.json"}) + "\n"]
        return mock.patch("voice_service.jobs.subprocess.Popen", return_value=FakeProcess(lines))

    def submit(self, jobs):
        import uuid
        return jobs.submit({"job_id": str(uuid.uuid4()), "concept_id": "c1"})["id"]

    def test_a_ready_lesson_gets_its_lecture_recorded_and_stays_ready(self):
        seen = {}

        def prerender(lesson, should_stop, progress):
            seen["lesson"] = lesson
            seen["running"] = jobs.running
            seen["busy"] = not jobs.idle.is_set()
            seen["stop"] = should_stop()
            progress(1, 4)
            seen["row"] = jobs.get(key)
            return True

        jobs = self.jobs(prerender)
        key = self.submit(jobs)
        with self.process():
            jobs.run(key)
        self.assertIs(seen["lesson"], self.lesson)
        self.assertIsNone(seen["running"])  # a class starting now must not pause this finished job
        self.assertTrue(seen["busy"])       # but the voice is still taken, so nothing else uses it meanwhile
        self.assertFalse(seen["stop"])
        self.assertEqual((seen["row"]["status"], seen["row"]["lecture_done"], seen["row"]["lecture_total"]), ("ready", 1, 4))
        self.assertEqual(jobs.get(key)["status"], "ready")
        self.assertTrue(jobs.idle.is_set())

    def test_a_class_reserving_the_voice_stops_the_recording_and_the_finished_job_stays_ready(self):
        import threading as t
        import time
        jobs = self.jobs(None)
        delivery = self.submit(jobs)
        jobs.update(delivery, status="ready")
        outcome = {}

        def prerender(lesson, should_stop, progress):
            starter = t.Thread(target=lambda: outcome.setdefault("reserved", jobs.reserve(delivery)))
            starter.start()
            deadline = time.time() + 5
            while not should_stop() and time.time() < deadline:
                time.sleep(0.01)
            outcome["stopped"] = should_stop()
            return False

        jobs.prerender = prerender
        key = self.submit(jobs)
        with self.process():
            jobs.run(key)
        for _ in range(100):
            if "reserved" in outcome:
                break
            time.sleep(0.05)
        self.assertTrue(outcome["stopped"])
        self.assertEqual(outcome["reserved"], {"reserved": True})
        self.assertEqual(jobs.get(key)["status"], "ready")  # not "paused_for_delivery": it is not prepared again

    def test_a_failing_recording_never_fails_the_lesson(self):
        def prerender(lesson, should_stop, progress):
            raise RuntimeError("the voice crashed")

        jobs = self.jobs(prerender)
        key = self.submit(jobs)
        with self.process():
            jobs.run(key)
        row = jobs.get(key)
        self.assertEqual((row["status"], row["percent"]), ("ready", 100))
        self.assertTrue(jobs.idle.is_set())

    def test_without_a_recorder_a_ready_lesson_is_unchanged(self):
        jobs = self.jobs(None)
        key = self.submit(jobs)
        with self.process():
            jobs.run(key)
        self.assertNotIn("lecture_done", jobs.get(key))
        self.assertEqual(jobs.get(key)["status"], "ready")


@unittest.skipUnless(lecture.shutil.which("node") and lecture.PLANNER.is_file(), "Node is needed for the gesture planner")
class RealPlannerTests(unittest.TestCase):
    def test_the_browsers_planner_runs_under_node(self):
        parts = [{"kind": "hook", "seed": 0, "sentences": [
            {"caption": "Your mission starts today, detective!", "startMs": 143, "speechMs": 1800},
            {"caption": "Can you see the pattern?", "startMs": 6000, "speechMs": 1500},
        ]}]
        plans = plan_gestures(parts)
        self.assertIsNotNone(plans)
        self.assertEqual(plans[0][0]["name"], "✋")  # the hook opens with a wave
        self.assertEqual(plans[0][0]["atMs"], 143)
        self.assertTrue(all(g["seconds"] > 0 for g in plans[0]))

    def test_node_failure_means_no_plan_not_a_crash(self):
        self.assertIsNone(plan_gestures([{"kind": "hook", "seed": 0, "sentences": []}], node="definitely-not-node"))


if __name__ == "__main__":
    unittest.main()
