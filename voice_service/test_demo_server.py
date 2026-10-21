import base64
import hashlib
import http.client
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from .demo_server import DEMO_JOB_ID, SAMPLE_RATE, DemoJobs, ReplayNarrator
from .record_demo_audio import record
from .service import VOICES, handler_for

ROOT = Path(__file__).resolve().parents[1]


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def lesson_fixture():
    return {
        "title": "Pairs to ten", "concept_id": "math_g2_m1_l1_pairs_to_ten", "grade": 2,
        "subject": "math", "preview_only": True, "ready_for_delivery": False,
        "voices": [{"id": k, "label": v} for k, v in VOICES.items()],
        "segments": [
            {"id": "s1", "kind": "lecture", "checkpoint": False, "cues": [], "review_flags": [],
             "utterances": [{"caption": "Seven and three make ten.", "spoken": "Seven and three make ten."},
                            {"caption": "Let us look again.", "spoken": "Let us look again."}]},
            {"id": "s2", "kind": "question", "checkpoint": True, "cues": [], "review_flags": [],
             "utterances": [{"caption": "What goes with six?", "spoken": "What goes with six?"}]},
        ],
    }


def pcm_frame(index, caption, spoken, samples=2400, value=1000):
    pcm = (value.to_bytes(2, "little", signed=True)) * samples
    return {"type": "audio", "utterance": index, "caption": caption, "sample_rate": SAMPLE_RATE,
            "pcm_s16le": base64.b64encode(pcm).decode(), "ready_after_s": 0.1,
            "spoken_sha256": sha(spoken)}


def write_recording(folder, voice, segment_id, frames):
    path = Path(folder) / voice / (segment_id + ".ndjson")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(f) + "\n" for f in frames))


def audio_of(frames):
    return [f for f in frames if f["type"] == "audio"]


def pcm_bytes(frame):
    return base64.b64decode(frame["pcm_s16le"])


class DemoJobsTests(unittest.TestCase):
    def test_the_fixed_id_passes_the_frontend_proxy_pattern(self):
        import re
        self.assertRegex(DEMO_JOB_ID, r"^[0-9a-f-]{36}$")
        self.assertTrue(re.fullmatch(r"[0-9a-f-]{36}", DEMO_JOB_ID))

    def test_serves_only_its_own_lesson(self):
        jobs = DemoJobs(lesson_fixture())
        self.assertEqual(jobs.lesson(DEMO_JOB_ID)["concept_id"], "math_g2_m1_l1_pairs_to_ten")
        with self.assertRaises(ValueError):
            jobs.lesson("11111111-1111-4111-8111-111111111111")
        self.assertEqual(jobs.reserve(DEMO_JOB_ID), {"reserved": True})
        self.assertEqual(jobs.release(DEMO_JOB_ID), {"released": True})
        with self.assertRaises(ValueError):
            jobs.reserve("11111111-1111-4111-8111-111111111111")
        self.assertEqual(jobs.list_cards(), [])

    def test_it_never_prepares_lessons(self):
        jobs = DemoJobs(lesson_fixture())
        for action in (jobs.submit, jobs.retry, jobs.cancel):
            with self.assertRaises(ValueError) as caught:
                action({})
            self.assertIn("does not prepare", str(caught.exception))


class SilentFallbackTests(unittest.TestCase):
    def frames(self, narrator, lesson, index, voice="af_heart"):
        return list(narrator.frames(lesson["segments"][index], voice))

    def test_every_utterance_gets_timed_silence_in_the_player_format(self):
        lesson = lesson_fixture()
        frames = self.frames(ReplayNarrator(), lesson, 0)
        self.assertEqual([f["type"] for f in frames], ["start", "audio", "audio", "done"])
        self.assertEqual(frames[0]["segment_id"], "s1")
        for i, frame in enumerate(audio_of(frames)):
            self.assertEqual(frame["utterance"], i)
            self.assertEqual(frame["caption"], lesson["segments"][0]["utterances"][i]["caption"])
            self.assertEqual(frame["sample_rate"], SAMPLE_RATE)
            data = pcm_bytes(frame)
            self.assertTrue(data and len(data) % 2 == 0)
            self.assertEqual(set(data), {0})

    def test_silence_is_longer_for_longer_sentences(self):
        long_text = "This is a much longer sentence with many more words in it so it takes longer."
        lesson = lesson_fixture()
        lesson["segments"][0]["utterances"][1] = {"caption": long_text, "spoken": long_text}
        short, longer = audio_of(self.frames(ReplayNarrator(), lesson, 0))
        self.assertGreater(len(pcm_bytes(longer)), len(pcm_bytes(short)))

    def test_a_very_short_sentence_still_lasts_long_enough_to_see(self):
        lesson = lesson_fixture()
        lesson["segments"][1]["utterances"] = [{"caption": "Ten.", "spoken": "Ten."}]
        (frame,) = audio_of(self.frames(ReplayNarrator(), lesson, 1))
        self.assertGreaterEqual(len(pcm_bytes(frame)) / 2 / SAMPLE_RATE, 0.8)


class RecordedNarrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lesson = lesson_fixture()

    def recorded_s1(self, voice="af_heart", value=1000):
        utterances = self.lesson["segments"][0]["utterances"]
        write_recording(self.tmp.name, voice, "s1", [
            {"type": "start", "segment_id": "s1"},
            *[pcm_frame(i, u["caption"], u["spoken"], value=value) for i, u in enumerate(utterances)],
            {"type": "done", "segment_id": "s1"}])

    def test_recorded_audio_is_replayed_instead_of_silence(self):
        self.recorded_s1()
        frames = list(ReplayNarrator(self.tmp.name).frames(self.lesson["segments"][0], "af_heart"))
        self.assertEqual([f["type"] for f in frames], ["start", "audio", "audio", "done"])
        self.assertEqual(pcm_bytes(frames[1])[:2], (1000).to_bytes(2, "little"))
        self.assertNotIn("spoken_sha256", frames[1])

    def test_each_voice_has_its_own_recording(self):
        self.recorded_s1("af_heart", 1000)
        self.recorded_s1("am_michael", 2000)
        narrator = ReplayNarrator(self.tmp.name)
        female = audio_of(narrator.frames(self.lesson["segments"][0], "af_heart"))
        male = audio_of(narrator.frames(self.lesson["segments"][0], "am_michael"))
        self.assertEqual(pcm_bytes(female[0])[:2], (1000).to_bytes(2, "little"))
        self.assertEqual(pcm_bytes(male[0])[:2], (2000).to_bytes(2, "little"))

    def test_a_segment_without_a_recording_falls_back_to_silence(self):
        self.recorded_s1()
        frames = audio_of(ReplayNarrator(self.tmp.name).frames(self.lesson["segments"][1], "af_heart"))
        self.assertEqual(set(pcm_bytes(frames[0])), {0})

    def test_audio_for_edited_text_is_never_played(self):
        self.recorded_s1()
        self.lesson["segments"][0]["utterances"][0] = {"caption": "Eight and two make ten.",
                                                       "spoken": "Eight and two make ten."}
        frames = audio_of(ReplayNarrator(self.tmp.name).frames(self.lesson["segments"][0], "af_heart"))
        self.assertEqual(set(pcm_bytes(frames[0])), {0})

    def test_a_different_sentence_count_is_never_replayed(self):
        self.recorded_s1()
        self.lesson["segments"][0]["utterances"].append({"caption": "More.", "spoken": "More."})
        frames = audio_of(ReplayNarrator(self.tmp.name).frames(self.lesson["segments"][0], "af_heart"))
        self.assertEqual(len(frames), 3)
        self.assertEqual(set(pcm_bytes(frames[0])), {0})

    def test_damaged_recordings_are_ignored(self):
        utterances = self.lesson["segments"][0]["utterances"]
        good = [pcm_frame(i, u["caption"], u["spoken"]) for i, u in enumerate(utterances)]
        broken_variants = {
            "not json": "{nope\n",
            "bad sample rate": [{**good[0], "sample_rate": 5}, good[1]],
            "odd byte count": [{**good[0], "pcm_s16le": base64.b64encode(b"\x01\x02\x03").decode()}, good[1]],
            "empty audio": [{**good[0], "pcm_s16le": ""}, good[1]],
            "not base64": [{**good[0], "pcm_s16le": "***"}, good[1]],
            "wrong utterance index": [good[1], good[0]],
        }
        for name, content in broken_variants.items():
            with self.subTest(name):
                path = Path(self.tmp.name) / "af_heart" / "s1.ndjson"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content if isinstance(content, str) else "".join(json.dumps(f) + "\n" for f in content))
                frames = audio_of(ReplayNarrator(self.tmp.name).frames(self.lesson["segments"][0], "af_heart"))
                self.assertEqual(set(pcm_bytes(frames[0])), {0})

    def test_segment_ids_cannot_escape_the_recording_folder(self):
        folder = Path(self.tmp.name) / "recordings"
        (folder / "af_heart").mkdir(parents=True)
        outside = Path(self.tmp.name) / "outside.ndjson"
        outside.write_text(json.dumps(pcm_frame(0, "x", "x")) + "\n")
        # The file really is reachable through "..", so only the id check stops it.
        self.assertTrue((folder / "af_heart" / "../../outside.ndjson").is_file())
        segment = {"id": "../../outside", "utterances": [{"caption": "x", "spoken": "x"}]}
        frames = audio_of(ReplayNarrator(folder).frames(segment, "af_heart"))
        self.assertEqual(set(pcm_bytes(frames[0])), {0})

    def test_coverage_counts_recorded_segments_per_voice(self):
        self.recorded_s1("af_heart")
        coverage = ReplayNarrator(self.tmp.name).coverage(self.lesson)
        self.assertEqual(coverage["af_heart"], {"recorded": 1, "total": 2})
        self.assertEqual(coverage["am_michael"], {"recorded": 0, "total": 2})
        self.assertEqual(ReplayNarrator().coverage(self.lesson)["af_heart"], {"recorded": 0, "total": 2})


class RecorderTests(unittest.TestCase):
    class StubNarrator:
        """Stands in for the Apple-only Kokoro narrator."""
        def __init__(self, short=False):
            self.short = short

        def frames(self, segment, voice):
            yield {"type": "start", "segment_id": segment["id"]}
            for i, u in enumerate(segment["utterances"][: (1 if self.short else None)]):
                yield {"type": "audio", "utterance": i, "caption": u["caption"], "sample_rate": SAMPLE_RATE,
                       "pcm_s16le": base64.b64encode(b"\x01\x02" * 100).decode(), "ready_after_s": 0.2}
            yield {"type": "done", "segment_id": segment["id"]}

    def test_a_recording_round_trips_through_the_replay_narrator(self):
        lesson = lesson_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            messages = []
            record(lesson, self.StubNarrator(), tmp, progress=messages.append)
            manifest = json.loads((Path(tmp) / "manifest.json").read_text())
            self.assertEqual(manifest["concept_id"], lesson["concept_id"])
            self.assertEqual(sorted(manifest["voices"]), ["af_heart", "am_michael"])
            self.assertEqual(manifest["segments"], ["s1", "s2"])
            narrator = ReplayNarrator(tmp)
            self.assertEqual(narrator.coverage(lesson)["am_michael"], {"recorded": 2, "total": 2})
            frames = audio_of(narrator.frames(lesson["segments"][0], "af_heart"))
            self.assertEqual(pcm_bytes(frames[0]), b"\x01\x02" * 100)
            self.assertTrue(messages)

    def test_a_segment_missing_audio_stops_the_recording_without_a_partial_file(self):
        lesson = lesson_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                record(lesson, self.StubNarrator(short=True), tmp)
            self.assertEqual(list(Path(tmp).rglob("*.ndjson")), [])
            self.assertEqual(list(Path(tmp).rglob("*.tmp")), [])
            self.assertFalse((Path(tmp) / "manifest.json").exists())

    def test_voices_can_be_limited(self):
        lesson = lesson_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            record(lesson, self.StubNarrator(), tmp, voices=["af_heart"])
            self.assertTrue((Path(tmp) / "af_heart" / "s1.ndjson").exists())
            self.assertFalse((Path(tmp) / "am_michael").exists())
        with self.assertRaises(ValueError):
            record(lesson, self.StubNarrator(), tempfile.gettempdir(), voices=["robot"])


class HttpTests(unittest.TestCase):
    """The unchanged service handler, driven by the demo job store and replay narrator."""

    def setUp(self):
        self.lesson = lesson_fixture()
        handler = handler_for(self.lesson, ReplayNarrator(), jobs=DemoJobs(self.lesson))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def call(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        conn.request(method, path, body=None if body is None else json.dumps(body),
                     headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response.status, data

    def test_the_routes_the_lesson_demo_page_uses(self):
        status, data = self.call("GET", "/health")
        self.assertEqual(status, 200)
        status, data = self.call("GET", f"/jobs/{DEMO_JOB_ID}/lesson")
        self.assertEqual(status, 200)
        self.assertEqual([s["id"] for s in json.loads(data)["segments"]], ["s1", "s2"])
        self.assertEqual(self.call("POST", f"/jobs/{DEMO_JOB_ID}/reserve", {})[0], 200)
        status, data = self.call("POST", "/narrate", {"segment_id": "s1", "voice": "af_heart", "job_id": DEMO_JOB_ID})
        self.assertEqual(status, 200)
        frames = [json.loads(line) for line in data.decode().splitlines()]
        self.assertEqual([f["type"] for f in frames], ["start", "audio", "audio", "done"])
        self.assertEqual(self.call("POST", f"/jobs/{DEMO_JOB_ID}/release", {})[0], 200)

    def test_unknown_segment_voice_and_job_are_refused(self):
        bad = {"segment_id": "nope", "voice": "af_heart", "job_id": DEMO_JOB_ID}
        self.assertEqual(self.call("POST", "/narrate", bad)[0], 400)
        self.assertEqual(self.call("POST", "/narrate", {**bad, "segment_id": "s1", "voice": "robot"})[0], 400)
        self.assertEqual(self.call("GET", "/jobs/11111111-1111-4111-8111-111111111111/lesson")[0], 409)

    def test_creating_a_job_is_refused_with_a_clear_message(self):
        status, data = self.call("POST", "/jobs", {"concept_id": "x"})
        self.assertEqual(status, 400)
        self.assertIn("does not prepare", json.loads(data)["detail"])


class PortabilityTests(unittest.TestCase):
    def test_importing_the_demo_needs_no_apple_audio_libraries(self):
        code = ("import sys, voice_service.demo_server, voice_service.record_demo_audio;"
                "bad=[m for m in sys.modules if m.split('.')[0] in ('mlx','mlx_audio','numpy')];"
                "sys.exit(1 if bad else 0)")
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_bundled_lesson_loads_and_has_a_demo_with_timed_silence(self):
        from .demo_server import DEFAULT_SCRIPT
        from .service import load_lesson
        lesson = load_lesson(DEFAULT_SCRIPT)
        self.assertEqual(len(lesson["segments"]), 19)
        narrator = ReplayNarrator()
        for segment in lesson["segments"]:
            frames = list(narrator.frames(segment, "am_michael"))
            self.assertEqual(len(audio_of(frames)), len(segment["utterances"]))


if __name__ == "__main__":
    unittest.main()
