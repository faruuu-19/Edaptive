"""Record the lesson's narration once, on an Apple Silicon Mac, for the portable demo.

The recording is plain local files for development. Keep them out of Git: pass a folder
outside the repository, or `demo-audio/` at the repository root, which is ignored.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .demo_server import DEFAULT_SCRIPT, spoken_hash
from .service import VOICES, load_lesson


def _write_atomically(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(text)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def record(lesson: dict, narrator, out_dir, voices=None, progress=print):
    out_dir = Path(out_dir)
    voices = list(voices or VOICES)
    unknown = [v for v in voices if v not in VOICES]
    if unknown:
        raise ValueError("Unknown teacher voice: " + ", ".join(unknown))
    total = len(voices) * len(lesson["segments"])
    done = 0
    for voice in voices:
        for segment in lesson["segments"]:
            audio = [f for f in narrator.frames(segment, voice) if f["type"] == "audio"]
            if len(audio) != len(segment["utterances"]):
                raise RuntimeError(f"{voice} produced {len(audio)} sentences for {segment['id']}; expected {len(segment['utterances'])}.")
            lines = [
                {**frame, "spoken_sha256": spoken_hash(utterance["spoken"])}
                for frame, utterance in zip(audio, segment["utterances"])
            ]
            _write_atomically(out_dir / voice / (segment["id"] + ".ndjson"), "".join(json.dumps(f) + "\n" for f in lines))
            done += 1
            progress(f"recorded {done}/{total}: {voice} {segment['id']}")
    _write_atomically(out_dir / "manifest.json", json.dumps({
        "format": 1, "concept_id": lesson["concept_id"], "voices": voices,
        "segments": [s["id"] for s in lesson["segments"]],
    }, indent=2) + "\n")


def main():
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", type=Path, default=DEFAULT_SCRIPT)
    parser.add_argument("--model", type=Path, default=Path.home() / "edaptive-voice/models/Kokoro-82M-bf16")
    parser.add_argument("--out", type=Path, default=Path.home() / "edaptive-voice/demo-audio")
    parser.add_argument("--voice", action="append", choices=sorted(VOICES), help="Limit to one voice (repeatable).")
    args = parser.parse_args()
    lesson = load_lesson(args.script)
    from .service import Narrator  # loads Apple MLX; only this command needs it

    record(lesson, Narrator(args.model), args.out, voices=args.voice)
    print(f"Done. Zip the folder {args.out} and send it privately; do not commit it.")


if __name__ == "__main__":
    main()
