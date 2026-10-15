"""Pre-compiled lectures: the teacher's narration for a lesson, recorded and timed ahead of class.

Without this, every sentence is spoken by the voice model while the child waits ("The teacher is getting ready to
speak"). With it, each part of a lesson is compiled once per voice and saved: the audio, where she is really speaking
inside each sentence, the pause between sentences, and the gestures that go with the words, all on one timeline.
Playing a compiled part is just reading it back, so it starts at once and always plays the same way.

A compiled part is two files in the store, named by a hash of the voice engine, the voice, the part id and its exact
text: `<part>-<hash>.json` (the timeline) and `<part>-<hash>.pcm` (the audio, raw 16-bit mono). Editing the script
changes the hash, so stale audio is never played. Both are teacher audio and lesson text only: no child data.

`CompilingNarrator` wraps the real narrator with the same interface. A part that is not compiled yet is spoken live
exactly as before and saved when it finishes, so the second play is instant even if nothing was pre-rendered.
`prerender_lesson` compiles a whole lesson ahead of time (after preparation) and stops at once if a class starts.
"""
from __future__ import annotations

import array
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

FORMAT = 1
GAP_MS = 1000  # silence between sentences; the browser applies it (frontend SENTENCE_GAP_MS)
SILENCE_LEVEL = 700  # samples quieter than this (~2% of full scale) are silence (frontend SILENCE_LEVEL)
REPO = Path(__file__).resolve().parents[1]
PLANNER = REPO / "tools" / "plan_gestures.mjs"
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")
RULES_FILES = (PLANNER, REPO / "frontend" / "src" / "features" / "avatar" / "gestures.mjs")
_fingerprint: list[str] = []


def pcm_ms(pcm: bytes, rate: int) -> float:
    return len(pcm) / 2 / rate * 1000


def speech_bounds(pcm: bytes, rate: int) -> tuple[float, float]:
    """Where speech starts and ends inside one sentence's audio; TTS pads both ends with silence."""
    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) // 2 * 2])
    if sys.byteorder == "big":
        samples.byteswap()
    total = pcm_ms(pcm, rate)
    first, last = 0, len(samples) - 1
    while first < len(samples) and abs(samples[first]) < SILENCE_LEVEL:
        first += 1
    while last > first and abs(samples[last]) < SILENCE_LEVEL:
        last -= 1
    if first >= last:
        return 0.0, total
    return first / rate * 1000, (last + 1) / rate * 1000


def rules_fingerprint() -> str:
    """A short hash of the gesture rules. It is part of every part's key, so editing the rules recompiles lessons
    instead of leaving gestures planned by the old rules in the store."""
    if not _fingerprint:
        digest = hashlib.sha256()
        for path in RULES_FILES:
            try:
                digest.update(bytes([10]).join(path.read_bytes().splitlines()))  # line endings do not change the hash
            except OSError:
                digest.update(b"-")
        _fingerprint.append(digest.hexdigest()[:12])
    return _fingerprint[0]


def plan_gestures(parts: list[dict], node: str | None = None, timeout: float = 30) -> list[list[dict]] | None:
    """The gesture plan for each part, from the same JavaScript the browser uses. None if Node is unavailable."""
    node = node or shutil.which("node")
    if not node or not PLANNER.is_file():
        return None
    try:
        done = subprocess.run(
            [node, str(PLANNER)], input=json.dumps({"parts": parts}), capture_output=True,
            text=True, encoding="utf-8", timeout=timeout, check=True,
        )
        plans = json.loads(done.stdout)["plans"]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        return None
    return plans if isinstance(plans, list) and len(plans) == len(parts) else None


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clean_gestures(raw) -> list[dict] | None:
    """Gestures read back from disk, checked so a damaged file can never reach the browser as nonsense."""
    if raw is None:
        return None
    clean = []
    for item in raw:
        try:
            at, seconds = float(item["at_ms"]), float(item["seconds"])
            name, mirror = item["name"], bool(item["mirror"])
        except (KeyError, TypeError, ValueError):
            return None
        if not isinstance(name, str) or not name or len(name) > 16 or not 0 <= at < 3_600_000 or not 0 < seconds <= 10:
            return None
        clean.append({"at_ms": round(at), "name": name, "seconds": round(seconds, 2), "mirror": mirror})
    return clean


class LectureStore:
    """Compiled parts on disk. Safe to share between voices and lessons: the key is the text, not the lesson."""

    def __init__(self, root, engine: str, max_bytes: int | None = None):
        self.engine = engine
        self.root = Path(root) / re.sub(r"[^A-Za-z0-9_.-]", "_", engine)
        self.max_bytes = max_bytes
        self.lock = threading.Lock()

    def key(self, segment: dict, voice: str) -> str:
        texts = [[u["spoken"], u["caption"]] for u in segment["utterances"]]
        return _hash(json.dumps([FORMAT, rules_fingerprint(), self.engine, voice, segment["id"], texts], ensure_ascii=False))[:24]

    @staticmethod
    def _part_name(segment: dict) -> str:
        return segment["id"] if SAFE_NAME.match(str(segment["id"])) else _hash(str(segment["id"]))[:24]

    def _paths(self, segment: dict, voice: str) -> tuple[Path, Path]:
        stem = f"{self._part_name(segment)}-{self.key(segment, voice)}"
        return self.root / voice / (stem + ".json"), self.root / voice / (stem + ".pcm")

    def _read(self, segment: dict, voice: str, verify_audio: bool):
        """(meta, pcm) when this part is compiled and still matches the script, else None."""
        meta_path, pcm_path = self._paths(segment, voice)
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta["format"] != FORMAT or meta["key"] != self.key(segment, voice):
                return None
            sentences, utterances = meta["sentences"], segment["utterances"]
            if len(sentences) != len(utterances):
                return None
            total = 0
            for sentence, utterance in zip(sentences, utterances):
                size, rate = sentence["pcm_bytes"], sentence["sample_rate"]
                if (
                    not isinstance(size, int) or size <= 0 or size % 2 or not isinstance(rate, int)
                    or not 8000 <= rate <= 48000 or sentence["caption"] != utterance["caption"]
                    or sentence["spoken_sha256"] != _hash(utterance["spoken"])
                ):
                    return None
                total += size
            if pcm_path.stat().st_size != total:
                return None
            pcm = pcm_path.read_bytes() if verify_audio else b""
            if verify_audio and (len(pcm) != total or _hash_bytes(pcm) != meta["pcm_sha256"]):
                return None
            return meta, pcm
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def has(self, segment: dict, voice: str) -> bool:
        return self._read(segment, voice, verify_audio=False) is not None

    def frames(self, segment: dict, voice: str) -> list[dict] | None:
        """The part exactly as the narration endpoint streams it, plus one `lecture` frame with the saved timeline."""
        found = self._read(segment, voice, verify_audio=True)
        if found is None:
            return None
        meta, pcm = found
        gestures = _clean_gestures(meta.get("gestures"))
        if meta.get("gestures") is not None and gestures is None:
            return None
        try:
            os.utime(self._paths(segment, voice)[0])  # recently used: kept longest when space runs short
        except OSError:
            pass
        frames: list[dict] = [
            {"type": "start", "segment_id": segment["id"]},
            {
                "type": "lecture", "version": FORMAT, "gap_ms": meta["gap_ms"], "kind": meta.get("kind", ""),
                "sentences": [
                    {"utterance": i, "speech_start_ms": s["speech_start_ms"], "speech_end_ms": s["speech_end_ms"]}
                    for i, s in enumerate(meta["sentences"])
                ],
                "gestures": gestures,
            },
        ]
        cursor = 0
        for index, sentence in enumerate(meta["sentences"]):
            chunk = pcm[cursor:cursor + sentence["pcm_bytes"]]
            cursor += sentence["pcm_bytes"]
            frames.append({
                "type": "audio", "utterance": index, "caption": sentence["caption"], "sample_rate": sentence["sample_rate"],
                "pcm_s16le": base64.b64encode(chunk).decode(), "ready_after_s": 0.0,
            })
        frames.append({"type": "done", "segment_id": segment["id"]})
        return frames

    def build(self, segment: dict, voice: str, audio: list[tuple[int, bytes]], planner=plan_gestures) -> dict:
        """The timeline for a part: speech bounds, the gaps, and the gesture plan, all on one clock (ms from the start)."""
        utterances = segment["utterances"]
        if len(audio) != len(utterances):
            raise ValueError("Every sentence needs audio.")
        sentences, plan_input, offset = [], [], 0.0
        for index, ((rate, pcm), utterance) in enumerate(zip(audio, utterances)):
            if index:
                offset += GAP_MS
            start, end = speech_bounds(pcm, rate)
            sentences.append({
                "utterance": index, "caption": utterance["caption"], "spoken_sha256": _hash(utterance["spoken"]),
                "sample_rate": rate, "pcm_bytes": len(pcm), "speech_start_ms": round(start, 1), "speech_end_ms": round(end, 1),
            })
            plan_input.append({"caption": utterance["caption"], "startMs": offset + start, "speechMs": end - start})
            offset += pcm_ms(pcm, rate)
        # Different parts start their opening gestures from different places, so they vary across a lecture.
        seed = int(_hash(str(segment["id"]))[:8], 16) % 5
        plans = planner([{"kind": segment.get("kind", ""), "seed": seed, "sentences": plan_input}])
        gestures = None if plans is None else [
            {"at_ms": round(g["atMs"]), "name": g["name"], "seconds": round(g["seconds"], 2), "mirror": bool(g["mirror"])}
            for g in plans[0]
        ]
        return {
            "format": FORMAT, "engine": self.engine, "voice": voice, "segment_id": segment["id"], "kind": segment.get("kind", ""),
            "key": self.key(segment, voice), "gap_ms": GAP_MS, "sentences": sentences, "gestures": gestures,
            "pcm_sha256": _hash_bytes(b"".join(pcm for _, pcm in audio)), "duration_ms": round(offset),
        }

    def save(self, segment: dict, voice: str, audio: list[tuple[int, bytes]], planner=plan_gestures) -> dict:
        meta = self.build(segment, voice, audio, planner)
        meta_path, pcm_path = self._paths(segment, voice)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        pcm_tmp, meta_tmp = Path(str(pcm_path) + ".tmp"), Path(str(meta_path) + ".tmp")
        try:
            pcm_tmp.write_bytes(b"".join(pcm for _, pcm in audio))
            meta_tmp.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            os.replace(pcm_tmp, pcm_path)  # the audio lands first: a reader only trusts a part once its timeline exists
            os.replace(meta_tmp, meta_path)
        finally:
            for leftover in (pcm_tmp, meta_tmp):
                try:
                    leftover.unlink()
                except OSError:
                    pass
        self._forget_superseded(segment, voice, meta_path)
        if self.max_bytes:
            self.prune(self.max_bytes)
        return meta

    def _forget_superseded(self, segment: dict, voice: str, current: Path):
        """Delete this part's older compilations (the script or the gesture rules changed since). Matches the exact
        `<part>-<24 hex>.json|.pcm` names, so another part whose name merely starts the same way is never touched."""
        pattern = re.compile("^" + re.escape(self._part_name(segment)) + "-[0-9a-f]{24}[.](json|pcm)$")
        keep = current.name[: -len(".json")]
        for other in current.parent.iterdir():
            if pattern.match(other.name) and not other.name.startswith(keep + "."):
                try:
                    other.unlink()
                except OSError:
                    pass

    def prune(self, max_bytes: int):
        """Keep the store under a size by removing the least recently used compiled parts."""
        with self.lock:
            if not self.root.exists():
                return
            files = [p for p in self.root.rglob("*") if p.is_file()]
            total = sum(p.stat().st_size for p in files)
            groups: dict[str, list[Path]] = {}
            for path in files:  # a part is its .json and .pcm together; leftovers form groups of their own
                stem = str(path).rsplit(".", 1)[0] if path.suffix in (".json", ".pcm") else str(path)
                groups.setdefault(stem, []).append(path)
            for _, group in sorted(groups.items(), key=lambda item: min(q.stat().st_mtime for q in item[1])):
                if total <= max_bytes:
                    break
                for path in group:
                    total -= path.stat().st_size
                    path.unlink()


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _Collector:
    """Gathers one part's audio from a narrator's frames, merging chunks the voice split a sentence into."""

    def __init__(self, expected: int):
        self.expected = expected
        self.audio: dict[int, tuple[int, bytearray]] = {}
        self.finished = False
        self.failed = False

    def add(self, frame: dict):
        kind = frame.get("type")
        if kind == "error":
            self.failed = True
        elif kind == "done":
            self.finished = True
        elif kind == "audio":
            index, rate = frame["utterance"], frame["sample_rate"]
            pcm = base64.b64decode(frame["pcm_s16le"])
            if index in self.audio:
                if self.audio[index][0] != rate:
                    self.failed = True
                self.audio[index][1].extend(pcm)
            else:
                self.audio[index] = (rate, bytearray(pcm))

    def result(self) -> list[tuple[int, bytes]] | None:
        if self.failed or not self.finished or sorted(self.audio) != list(range(self.expected)):
            return None
        return [(rate, bytes(pcm)) for _, (rate, pcm) in sorted(self.audio.items())]


class CompilingNarrator:
    """The real narrator, plus a store of compiled parts. Same interface, so the service does not change."""

    def __init__(self, inner, store: LectureStore, planner=plan_gestures):
        self.inner, self.store, self.planner = inner, store, planner

    def __getattr__(self, name):  # lock, warm, release, model_dir...: whatever the real narrator offers
        if name in ("inner", "store", "planner"):
            raise AttributeError(name)
        return getattr(self.inner, name)

    def frames(self, segment: dict, voice: str):
        cached = self.store.frames(segment, voice)
        if cached is not None:
            yield from cached
            return
        collected = _Collector(len(segment["utterances"]))
        for frame in self.inner.frames(segment, voice):
            collected.add(frame)
            yield frame
        self._save(segment, voice, collected)  # only reached when the child heard the whole part

    def _save(self, segment, voice, collected: _Collector) -> bool:
        audio = collected.result()
        if audio is None:
            return False
        try:
            self.store.save(segment, voice, audio, self.planner)
        except (OSError, ValueError):
            return False  # saving is a bonus; it must never break the narration
        return True

    def render(self, segment: dict, voice: str, should_stop=None) -> bool:
        """Compile one part now. False if stopped part-way (nothing is saved) or the voice failed."""
        collected = _Collector(len(segment["utterances"]))
        for frame in self.inner.frames(segment, voice):
            if should_stop and should_stop():
                return False
            collected.add(frame)
        return self._save(segment, voice, collected)

    def prerender_lesson(self, lesson: dict, voices, should_stop=None, progress=None) -> bool:
        """Compile every part of a lesson for each voice. Returns False if it stopped early, e.g. a class is starting.

        Stops between sentences, so a class never waits more than one sentence. Parts already compiled are skipped,
        so it can be called again to finish. Holds the narrator's lock only while one part renders.
        """
        segments, voices = lesson["segments"], list(voices)
        total, done = len(segments) * len(voices), 0
        for voice in voices:
            for segment in segments:
                if should_stop and should_stop():
                    return False
                if not self.store.has(segment, voice):
                    if not self.inner.lock.acquire(timeout=2):
                        return False  # the teacher is busy with a class
                    try:
                        if not self.render(segment, voice, should_stop):
                            return False
                    finally:
                        self.inner.lock.release()
                done += 1
                if progress:
                    progress(done, total)
        return True
