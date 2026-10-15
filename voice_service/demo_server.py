"""Portable lesson demo: the voice service's routes without Kokoro, MLX, Ollama or Postgres.

It serves one saved, checked script to the unchanged `/lesson-demo` page. Narration is
replayed from a local recording made once on an Apple Silicon Mac (see
`record_demo_audio.py`), or, where no recording exists, sent as silence timed to the words,
so the page and its timing work on any computer. It plays only the saved script: it cannot
prepare lessons and it records nothing.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
import struct
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from .service import VOICES, handler_for, load_lesson

# Matches the frontend proxy's accepted pattern for EDAPTIVE_DEMO_JOB_ID.
DEMO_JOB_ID = "0de30de3-0de3-4de3-8de3-0de30de30de3"
SAMPLE_RATE = 24000
WORDS_PER_SECOND = 2.5
MIN_UTTERANCE_SECONDS = 0.8
DEFAULT_SCRIPT = Path(__file__).resolve().parents[1] / "examples/lessons/grade2-module1-lesson1.script.json"
SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def spoken_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class DemoJobs:
    """The job-store routes the page uses, for the one saved lesson."""

    def __init__(self, lesson: dict, key: str = DEMO_JOB_ID):
        self._lesson, self.key = lesson, key

    def _check(self, key: str):
        if key != self.key:
            raise ValueError("This demo only plays its saved lesson.")

    def lesson(self, key):
        self._check(key)
        return self._lesson

    def public(self, key):
        self._check(key)
        return {"id": key, "status": "ready", "demo": True}

    def reserve(self, key):
        self._check(key)
        return {"reserved": True}

    def release(self, key):
        self._check(key)
        return {"released": True}

    def list_cards(self):
        return []

    def _refuse(self, *_args):
        raise ValueError("The demo does not prepare lessons; it only plays its saved lesson.")

    submit = retry = cancel = _refuse


class ReplayNarrator:
    """Same interface as the Kokoro narrator: a `lock` and `frames(segment, voice)`."""

    def __init__(self, audio_dir=None):
        self.audio_dir = Path(audio_dir) if audio_dir else None
        self.lock = threading.Lock()

    def warm(self):
        pass

    def release(self):
        pass

    @staticmethod
    def _valid_audio(frame, index: int):
        if not isinstance(frame, dict) or frame.get("type") != "audio" or frame.get("utterance") != index:
            return None
        rate = frame.get("sample_rate")
        if not isinstance(rate, int) or isinstance(rate, bool) or not 8000 <= rate <= 48000:
            return None
        try:
            data = base64.b64decode(frame.get("pcm_s16le", ""), validate=True)
        except (binascii.Error, TypeError, ValueError):
            return None
        return (rate, data) if data and len(data) % 2 == 0 else None

    def _recorded(self, segment: dict, voice: str):
        """The recorded frames for this segment, or None unless they match its current text."""
        segment_id = str(segment["id"])
        if self.audio_dir is None or voice not in VOICES or not SAFE_ID.fullmatch(segment_id):
            return None
        path = self.audio_dir / voice / (segment_id + ".ndjson")
        try:
            lines = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        except (OSError, ValueError):
            return None
        audio = [f for f in lines if isinstance(f, dict) and f.get("type") == "audio"]
        utterances = segment["utterances"]
        if len(audio) != len(utterances):
            return None
        frames = []
        for index, (frame, utterance) in enumerate(zip(audio, utterances)):
            checked = self._valid_audio(frame, index)
            if checked is None or frame.get("spoken_sha256") != spoken_hash(utterance["spoken"]):
                return None
            frames.append({
                "type": "audio", "utterance": index, "caption": utterance["caption"],
                "sample_rate": checked[0], "pcm_s16le": frame["pcm_s16le"], "ready_after_s": 0.0,
            })
        return frames

    @staticmethod
    def _silence(segment: dict):
        for index, utterance in enumerate(segment["utterances"]):
            seconds = max(MIN_UTTERANCE_SECONDS, len(utterance["spoken"].split()) / WORDS_PER_SECOND)
            pcm = struct.pack("<h", 0) * round(seconds * SAMPLE_RATE)
            yield {
                "type": "audio", "utterance": index, "caption": utterance["caption"],
                "sample_rate": SAMPLE_RATE, "pcm_s16le": base64.b64encode(pcm).decode(),
                "ready_after_s": 0.0,
            }

    def frames(self, segment: dict, voice: str):
        yield {"type": "start", "segment_id": segment["id"]}
        recorded = self._recorded(segment, voice)
        yield from recorded if recorded is not None else self._silence(segment)
        yield {"type": "done", "segment_id": segment["id"]}

    def coverage(self, lesson: dict) -> dict:
        total = len(lesson["segments"])
        return {
            voice: {"recorded": sum(self._recorded(s, voice) is not None for s in lesson["segments"]), "total": total}
            for voice in VOICES
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", type=Path, default=DEFAULT_SCRIPT, help="Saved script-0.1 draft to play.")
    parser.add_argument("--audio-dir", type=Path, help="Recorded narration folder (from record_demo_audio.py).")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    lesson = load_lesson(args.script)
    narrator = ReplayNarrator(args.audio_dir)
    for voice, counts in narrator.coverage(lesson).items():
        label = "recorded narration" if counts["recorded"] else "silent timing only"
        print(f"{VOICES[voice]}: {counts['recorded']} of {counts['total']} segments, {label}", flush=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(lesson, narrator, jobs=DemoJobs(lesson)))
    print(f"Portable lesson demo ready at http://127.0.0.1:{args.port} (demo job {DEMO_JOB_ID})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
