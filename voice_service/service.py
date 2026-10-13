"""Loopback-only draft lesson preview. No student input, saved audio, or event writes."""

from __future__ import annotations

import argparse
import base64
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.parse import parse_qs

from .speech_prep import prepare_segment

VOICES = {"af_heart": "Female teacher", "am_michael": "Male teacher"}


def load_lesson(path: Path) -> dict:
    script = json.loads(path.read_text())
    if (
        script.get("schema_version") != "script-0.1"
        or script.get("validation", {}).get("passed") is not True
    ):
        raise ValueError(
            "The preview requires a script-0.1 draft with passing script checks."
        )
    bank = {s["id"]: s for s in script["segments"]}
    ids = script["delivery_policy"]["main_path"]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("The script must have a unique, nonempty main path.")
    segments = []
    for sid in ids:
        source = bank[sid]
        if (
            source.get("condition")
            or source.get("conditions")
            or source.get("phase") == "conditional"
        ):
            raise ValueError("Conditional answers cannot enter the preview main path.")
        prepared = prepare_segment(source["text"])
        visual = source.get("visual_cue")
        cues = list(prepared.cues)
        if isinstance(visual, str):
            cues.extend(prepare_segment(visual).cues)
        elif visual is not None:
            raise ValueError(
                "Unsupported visual cue; review its shape before previewing."
            )
        if any(
            f.startswith(
                ("unspoken_digits:", "unspoken_symbol:", "template_marker_removed")
            )
            for f in prepared.review_flags
        ):
            raise ValueError("Speech preparation needs review for " + sid)
        segments.append(
            {
                "id": sid,
                "kind": source["type"],
                "checkpoint": bool(source.get("question_id"))
                or source.get("phase") == "your_turn",
                "utterances": [
                    {"caption": u.caption, "spoken": u.spoken}
                    for u in prepared.utterances
                ],
                "cues": list(dict.fromkeys(cues)),
                "review_flags": list(prepared.review_flags),
            }
        )
    from .timing import estimate_timing

    timing = {**estimate_timing(segments, script["grade"]), "basis": "prepared_script"}
    title = script["concept_id"].split("_", 4)[-1].replace("_", " ").capitalize()
    return {
        "title": title,
        "concept_id": script["concept_id"],
        "grade": script["grade"],
        "subject": script["subject"],
        "preview_only": True,
        "ready_for_delivery": False,
        "input_readiness": script.get("input_readiness"),
        "segments": segments,
        "timing": timing,
        "voices": [{"id": key, "label": value} for key, value in VOICES.items()],
    }


class Narrator:
    def __init__(self, model_dir: Path):
        self.model_dir = model_dir
        self.model = None
        self.lock = threading.Lock()
        self.warm()

    def warm(self):
        from mlx_audio.tts.utils import load_model

        with self.lock:
            if self.model is None:
                self.model = load_model(str(self.model_dir))
                list(
                    self.model.generate(
                        text="Let us learn together.",
                        voice=self.voice_path("af_heart"),
                        speed=1.0,
                        lang_code="a",
                    )
                )

    def release(self):
        import gc
        import mlx.core as mx

        if not self.lock.acquire(blocking=False):
            raise ValueError(
                "Finish the current narration before preparing another class."
            )
        try:
            self.model = None
            gc.collect()
            mx.clear_cache()
        finally:
            self.lock.release()

    def voice_path(self, voice: str) -> str:
        if voice not in VOICES:
            raise ValueError("Unknown teacher voice.")
        path = self.model_dir / "voices" / (voice + ".safetensors")
        if not path.is_file():
            raise ValueError("The selected local teacher voice is missing.")
        return str(path)

    def frames(self, segment: dict, voice: str):
        import numpy as np

        if self.model is None:
            raise RuntimeError(
                "The teacher is preparing the scheduled class. Please wait."
            )
        start = time.perf_counter()
        yield {"type": "start", "segment_id": segment["id"]}
        for index, utterance in enumerate(segment["utterances"]):
            for result in self.model.generate(
                text=utterance["spoken"],
                voice=self.voice_path(voice),
                speed=1.0,
                lang_code="a",
            ):
                samples = np.asarray(result.audio, dtype=np.float32).reshape(-1)
                if samples.size == 0 or not np.isfinite(samples).all():
                    raise RuntimeError("The voice produced invalid audio.")
                pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
                yield {
                    "type": "audio",
                    "utterance": index,
                    "caption": utterance["caption"],
                    "sample_rate": result.sample_rate,
                    "pcm_s16le": base64.b64encode(pcm.tobytes()).decode(),
                    "ready_after_s": round(time.perf_counter() - start, 3),
                }
        yield {"type": "done", "segment_id": segment["id"]}


def handler_for(lesson: dict, narrator, timetable=None, jobs=None):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            pass  # No request text, learner identifiers or audio logged.

        def reply(self, status: int, data: dict):
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def valid_origin(self) -> bool:
            origin = self.headers.get("Origin")
            return not origin or urlparse(origin).hostname in {
                "localhost",
                "127.0.0.1",
                "::1",
            }

        def do_GET(self):
            if not self.valid_origin():
                return self.reply(403, {"detail": "Local preview only."})
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/health":
                return self.reply(
                    200, {"ready": True, "model": "kokoro", "preview_only": True}
                )
            if (jobs or timetable) and path == "/catalog":
                return self.reply(
                    200,
                    {"cards": jobs.list_cards() if jobs else timetable.list_cards()},
                )
            if timetable and path == "/schedule":
                return self.reply(200, timetable.snapshot())
            if jobs and path.startswith("/jobs/"):
                parts = path.strip("/").split("/")
                try:
                    data = (
                        jobs.lesson(parts[1])
                        if len(parts) == 3 and parts[2] == "lesson"
                        else jobs.public(parts[1])
                    )
                    return self.reply(200, data)
                except (ValueError, KeyError):
                    return self.reply(409, {"detail": "Preparation job is not ready."})
            if path == "/lesson":
                if lesson is None:
                    return self.reply(
                        404, {"detail": "Use the authenticated scheduled lesson."}
                    )
                sid = parse_qs(parsed.query).get("schedule_id", [None])[0]
                try:
                    return self.reply(
                        200, timetable.lesson(sid) if sid and timetable else lesson
                    )
                except ValueError as error:
                    return self.reply(409, {"detail": str(error)})
            self.reply(404, {"detail": "Unknown preview endpoint."})

        def do_POST(self):
            if self.path not in {
                "/narrate",
                "/schedule",
                "/schedule-action",
                "/jobs",
            } and not self.path.startswith("/jobs/"):
                return self.reply(404, {"detail": "Unknown preview endpoint."})
            if not self.valid_origin():
                return self.reply(403, {"detail": "Local preview only."})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1024:
                    raise ValueError("Invalid preview request size.")
                request = json.loads(self.rfile.read(length))
                if not isinstance(request, dict):
                    raise ValueError("A request object is required.")
                if jobs and self.path == "/jobs":
                    return self.reply(200, jobs.submit(request))
                if jobs and self.path.startswith("/jobs/"):
                    parts = self.path.strip("/").split("/")
                    if len(parts) != 3:
                        raise ValueError("Unknown job action.")
                    if parts[2] == "retry":
                        return self.reply(200, jobs.retry(parts[1]))
                    if parts[2] == "cancel":
                        return self.reply(200, jobs.cancel(parts[1]))
                    if parts[2] == "reserve":
                        return self.reply(200, jobs.reserve(parts[1]))
                    if parts[2] == "release":
                        return self.reply(200, jobs.release(parts[1]))
                    raise ValueError("Unknown job action.")
                if self.path in {"/schedule", "/schedule-action"}:
                    if not timetable:
                        raise ValueError("Timetable preview is unavailable.")
                    data = (
                        timetable.create(request)
                        if self.path == "/schedule"
                        else timetable.action(request)
                    )
                    return self.reply(200, data)
                if (
                    set(request)
                    not in (
                        {"segment_id", "voice"},
                        {"segment_id", "voice", "schedule_id"},
                        {"segment_id", "voice", "job_id"},
                    )
                    or request["voice"] not in VOICES
                ):
                    raise ValueError(
                        "Choose a main-path segment and a supported teacher voice."
                    )
                active = (
                    jobs.lesson(request["job_id"])
                    if request.get("job_id") and jobs
                    else timetable.lesson(request["schedule_id"])
                    if request.get("schedule_id") and timetable
                    else lesson
                )
                segment = next(
                    (s for s in active["segments"] if s["id"] == request["segment_id"]),
                    None,
                )
                if segment is None:
                    raise ValueError("This segment is not in the lesson main path.")
            except (ValueError, TypeError, KeyError) as error:
                return self.reply(
                    400,
                    {
                        "detail": str(error)
                        if self.path != "/narrate"
                        else "Invalid preview segment or voice."
                    },
                )
            if not narrator.lock.acquire(blocking=False):
                return self.reply(
                    409,
                    {
                        "detail": "The teacher is finishing another request. Please try again."
                    },
                )
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True
                for frame in narrator.frames(segment, request["voice"]):
                    self.wfile.write((json.dumps(frame) + "\n").encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                try:
                    self.wfile.write(
                        b'{"type":"error","detail":"Narration stopped. Please retry."}\n'
                    )
                    self.wfile.flush()
                except OSError:
                    pass
            finally:
                narrator.lock.release()

    return Handler


def main():
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--script",
        type=Path,
        help="Optional manual review script; scheduled jobs do not use it.",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=Path.home() / "edaptive-voice/models/Kokoro-82M-bf16",
    )
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument(
        "--content-root",
        type=Path,
        default=Path.home() / "Downloads/edaptive-assessment-card-generator",
    )
    args = parser.parse_args()
    lesson = load_lesson(args.script) if args.script else None
    narrator = Narrator(args.model)
    from .jobs import PreparationJobs

    jobs = PreparationJobs(args.content_root, narrator, load_lesson)
    server = ThreadingHTTPServer(
        ("127.0.0.1", args.port), handler_for(lesson, narrator, jobs=jobs)
    )
    print(
        f"Local Kokoro lesson preview ready at http://127.0.0.1:{args.port}", flush=True
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
