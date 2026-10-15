"""Run the lesson demo with sound, the 3D teachers and compiled lectures. Works on any computer with Node and Python.

    python tools/dev_demo/run.py [--voice windows|edge] [--prerender] [--no-cache]

Starts the stand-in voice server (`serve.py`) and the Next.js frontend, then prints the page address. Ctrl+C stops both.
The default voice is the offline Windows one on Windows and the online Edge one elsewhere. See README.md in this folder.
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from run_lesson_demo import build_plan, preflight, stop, wait_for  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--voice", choices=("windows", "edge"), default="windows" if sys.platform == "win32" else "edge")
    parser.add_argument("--prerender", action="store_true", help="compile the whole lesson in the background")
    parser.add_argument("--no-cache", action="store_true", help="speak every sentence live")
    parser.add_argument("--web-port", type=int, default=3001)
    parser.add_argument("--voice-port", type=int, default=8766)
    args = parser.parse_args()

    npm = shutil.which("npm")
    problems = preflight(ROOT, npm, None, None)
    if problems:
        sys.exit("\n".join(problems))
    plan = build_plan(ROOT, sys.executable, npm, args.voice_port, args.web_port, None, None)
    env = dict(os.environ, PYTHONUTF8="1")

    voice_command = [sys.executable, "-B", str(HERE / "serve.py"), "--voice", args.voice, "--port", str(args.voice_port)]
    voice_command += [flag for flag, on in (("--prerender", args.prerender), ("--no-cache", args.no_cache)) if on]
    voice = subprocess.Popen(voice_command, cwd=ROOT, env=env)
    web = subprocess.Popen(plan["web"]["args"], cwd=plan["web"]["cwd"], env=dict(env, **plan["web"]["env"]))
    page = f"http://127.0.0.1:{args.web_port}/lesson-demo"
    try:
        if wait_for(page, [voice, web], 120):
            print(f"\nOpen {page} in your browser and press Listen.  (Ctrl+C stops both)", flush=True)
        while voice.poll() is None and web.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        stop(web)
        stop(voice)


if __name__ == "__main__":
    main()
