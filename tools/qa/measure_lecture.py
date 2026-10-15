"""Time how long a child waits for the first sound, compiled versus live, through the real frontend.

    python tools/qa/measure_lecture.py [--store tools/dev_demo/lectures/<engine>]

Start the demo with `python tools/dev_demo/run.py --prerender` and wait for "prerender finished". It then asks for every
part of the demo lesson in both voices (all should come from the compiled store), and for one part three ways:
compiled, then with its compiled files removed (so it is spoken live and saved), then compiled again.
Only needs the standard library.
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from voice_service.demo_server import DEMO_JOB_ID  # noqa: E402


def narrate(frontend, segment_id, voice):
    request = urllib.request.Request(
        f"{frontend}/voice-preview-api/narrate", headers={"Content-Type": "application/json"},
        data=json.dumps({"segment_id": segment_id, "voice": voice}).encode())
    started, first, kinds, lecture = time.time(), None, [], None
    with urllib.request.urlopen(request, timeout=120) as response:
        for line in response:
            frame = json.loads(line)
            kinds.append(frame["type"])
            if frame["type"] == "audio" and first is None:
                first = time.time() - started
            if frame["type"] == "lecture":
                lecture = frame
    return first, kinds, lecture


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--frontend", default="http://127.0.0.1:3001")
    parser.add_argument("--voice-service", default="http://127.0.0.1:8766")
    parser.add_argument("--store", type=Path, help="the compiled-lecture folder of the engine in use")
    args = parser.parse_args()

    lesson = json.load(urllib.request.urlopen(f"{args.voice_service}/jobs/{DEMO_JOB_ID}/lesson"))
    parts = lesson["segments"]
    firsts = []
    for voice in ("af_heart", "am_michael"):
        for part in parts:
            first, kinds, lecture = narrate(args.frontend, part["id"], voice)
            if lecture is None:
                sys.exit(f"Part {part['id']} ({voice}) was not compiled yet. Wait for 'prerender finished' and run again.")
            firsts.append(first)
    print(f"compiled: {len(parts)} parts x 2 voices; first sound after avg {1000 * sum(firsts) / len(firsts):.0f} ms, max {1000 * max(firsts):.0f} ms")

    if args.store:
        part = parts[3]["id"]
        compiled, _, _ = narrate(args.frontend, part, "af_heart")
        for path in args.store.rglob(f"{part}-*"):
            if path.parent.name == "af_heart":
                os.remove(path)
        live, live_kinds, _ = narrate(args.frontend, part, "af_heart")  # spoken live, and saved when it finishes
        time.sleep(0.5)
        again, _, _ = narrate(args.frontend, part, "af_heart")
        print(f"part {part!r}: compiled {1000 * compiled:.0f} ms | live {1000 * live:.0f} ms ({','.join(live_kinds)}) | compiled again {1000 * again:.0f} ms")


if __name__ == "__main__":
    main()
