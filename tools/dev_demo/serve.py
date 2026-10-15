"""Serve the demo lesson's narration with a stand-in voice, with compiled lectures in front of it.

    python tools/dev_demo/serve.py --voice windows|edge [--prerender] [--no-cache]

This is the voice side of the development demo (`run.py` starts it together with the frontend). It plays the one saved
demo lesson, like `voice_service/demo_server.py`, but speaks with a stand-in voice, so you hear the teacher without the
Kokoro model, and wraps the voice in `voice_service.lecture.CompilingNarrator`, so lectures are compiled and played back
exactly as in the real service.

--prerender   compile every part of the lesson for both voices in the background, as the job runner does after a
              lesson is prepared. Without it, a part is compiled the first time it is spoken.
--no-cache    speak every sentence live, with no compiled lectures.
"""
import argparse
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))  # the voice_service package
sys.path.insert(0, str(HERE))

ENGINES = {"edge": "edge-tts-neural-v1", "windows": "windows-sapi-v1"}  # part of every compiled part's key


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--voice", choices=sorted(ENGINES), default="windows" if sys.platform == "win32" else "edge",
                        help="windows: the built-in Windows voices, offline. edge: Microsoft Edge neural voices, ONLINE.")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--script", type=Path, help="a saved script-0.1 lesson (default: the bundled demo lesson)")
    parser.add_argument("--store", type=Path, default=HERE / "lectures", help="where compiled lectures are kept")
    parser.add_argument("--prerender", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    from voice_service.demo_server import DEFAULT_SCRIPT, DemoJobs
    from voice_service.lecture import CompilingNarrator, LectureStore
    from voice_service.service import VOICES, handler_for, load_lesson

    if args.voice == "windows":
        if sys.platform != "win32":
            sys.exit("The windows voice only works on Windows. Use --voice edge (online) or the real Kokoro service.")
        from windows_voice import WindowsNarrator as Narrator
    else:
        try:
            from edge_voice import EdgeNarrator as Narrator
        except ImportError:
            sys.exit("The edge voice needs two packages: pip install -r tools/dev_demo/requirements.txt")

    lesson = load_lesson(args.script or DEFAULT_SCRIPT)
    narrator = Narrator(None)
    if not args.no_cache:
        narrator = CompilingNarrator(narrator, LectureStore(args.store, ENGINES[args.voice]))
        if args.prerender:
            def record():
                started = time.time()
                done = narrator.prerender_lesson(
                    lesson, list(VOICES),
                    progress=lambda d, t: print(f"  compiled {d}/{t} ({time.time() - started:.0f}s)", flush=True))
                print("prerender finished" if done else "prerender stopped early", flush=True)
            threading.Thread(target=record, daemon=True).start()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(lesson, narrator, jobs=DemoJobs(lesson)))
    cache = "off" if args.no_cache else str(args.store)
    print(f"Demo voice ({args.voice}) ready on port {args.port}; compiled lectures: {cache}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
