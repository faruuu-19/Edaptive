#!/usr/bin/env python3
"""Start the portable /lesson-demo on any computer (Windows, macOS or Linux).

It runs the voice stand-in (no MLX, Ollama or Postgres) and the Next.js frontend, then
prints the page address. Use `python` on Windows and `python3` elsewhere.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DEMO_JOB_ID = "0de30de3-0de3-4de3-8de3-0de30de30de3"  # same value as voice_service.demo_server
DEFAULT_SCRIPT = Path("examples/lessons/grade2-module1-lesson1.script.json")


def build_plan(root, python, npm, voice_port, web_port, script, audio_dir):
    root = Path(root)
    voice = [str(python), "-m", "voice_service.demo_server", "--port", str(voice_port)]
    if script:
        voice += ["--script", str(script)]
    if audio_dir:
        voice += ["--audio-dir", str(audio_dir)]
    return {
        "voice": {"args": voice, "cwd": root, "env": {}},
        "web": {
            "args": [str(npm), "run", "dev", "--", "--hostname", "127.0.0.1", "--port", str(web_port)],
            "cwd": root / "frontend",
            "env": {
                "EDAPTIVE_VOICE_PREVIEW": "1",
                "EDAPTIVE_DEMO_JOB_ID": DEMO_JOB_ID,
                "EDAPTIVE_VOICE_URL": f"http://127.0.0.1:{voice_port}",
                "NEXT_TELEMETRY_DISABLED": "1",
            },
        },
    }


def preflight(root, npm, script, audio_dir):
    root, problems = Path(root), []
    if not npm:
        problems.append("Node.js 20.9 or newer is not installed (npm was not found). Install it from nodejs.org, then run this again.")
    if not (root / "frontend/node_modules").is_dir():
        problems.append("The frontend is not installed yet. Run `npm install` inside the frontend folder once, then run this again.")
    if not (Path(script) if script else root / DEFAULT_SCRIPT).is_file():
        problems.append("The saved lesson script was not found. Check that you have the whole repository.")
    if audio_dir and not Path(audio_dir).is_dir():
        problems.append(f"The narration recording folder {audio_dir} was not found. Unzip it first, or leave out --audio-dir for silent timing.")
    return problems


def stop(process):
    if process.poll() is not None:
        return
    if sys.platform == "win32":  # npm.cmd starts node as a child; end the whole tree
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def wait_for(url, processes, seconds):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if any(p.poll() is not None for p in processes):
            return False
        try:
            with urlopen(url, timeout=2):
                return True
        except (URLError, OSError):
            time.sleep(0.5)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio-dir", type=Path, help="Folder of recorded narration (optional). Without it the demo is silent but correctly timed.")
    parser.add_argument("--script", type=Path, help="A different saved script-0.1 draft (default: Grade 2 Module 1 Lesson 1).")
    parser.add_argument("--voice-port", type=int, default=8766)
    parser.add_argument("--web-port", type=int, default=3001)
    args = parser.parse_args()
    npm = shutil.which("npm")
    problems = preflight(ROOT, npm, args.script, args.audio_dir)
    if problems:
        print("Cannot start yet:\n- " + "\n- ".join(problems), file=sys.stderr)
        return 2
    plan = build_plan(ROOT, sys.executable, npm, args.voice_port, args.web_port, args.script, args.audio_dir)
    processes = []
    try:
        voice = subprocess.Popen(plan["voice"]["args"], cwd=plan["voice"]["cwd"])
        processes.append(voice)
        if not wait_for(f"http://127.0.0.1:{args.voice_port}/health", processes, 30):
            print("The voice stand-in did not start.", file=sys.stderr)
            return 1
        web = subprocess.Popen(plan["web"]["args"], cwd=plan["web"]["cwd"], env={**os.environ, **plan["web"]["env"]})
        processes.append(web)
        print(f"\nOpen http://127.0.0.1:{args.web_port}/lesson-demo (press Ctrl+C to stop both).\n", flush=True)
        while all(p.poll() is None for p in processes):
            time.sleep(1)
        print("One of the two programs stopped; shutting down.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        for process in reversed(processes):
            stop(process)


if __name__ == "__main__":
    sys.exit(main())
