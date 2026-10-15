# Development demo: the talking teacher with sound

Runs `/lesson-demo` with the 3D teachers, the 1 s pauses, gestures and **compiled lectures**, on any computer with Node
and Python, **without the Kokoro model**. It plays the one saved demo lesson (Grade 2, "Pairs to ten"). Background and
design: `docs/voice/TEACHER_AVATAR.md`.

> **Development only.** The real product speaks with Kokoro (local, offline). These stand-in voices exist so the teacher
> can be built and shown on a machine that cannot run Kokoro. The `edge` voice needs internet and breaks the project's
> offline rule; do not use it for anything a child sees.

## Run it

```sh
cd frontend && npm install && cd ..          # once

python tools/dev_demo/run.py --prerender     # then open http://127.0.0.1:3001/lesson-demo and press Listen
```

| Flag | Meaning |
|---|---|
| `--voice windows` | The built-in Windows voices (Zira and David). **Offline, nothing to install.** Default on Windows. |
| `--voice edge` | Microsoft Edge neural voices, **online**. More natural. Default elsewhere. Needs `pip install -r tools/dev_demo/requirements.txt`. |
| `--prerender` | Compile every part of the lesson for both voices in the background (about 1.5 to 3 minutes). Without it, a part is compiled the first time it is spoken. |
| `--no-cache` | Speak every sentence live (the behaviour before compiled lectures). |
| `--web-port`, `--voice-port` | If 3001 or 8766 is busy. |

Compiled lectures are written to `tools/dev_demo/lectures/` (git-ignored, about 21 MB for the whole lesson in both
voices). Delete the folder to start clean. Ctrl+C stops everything.

On Windows, if you run `tools/run_lesson_demo.py` instead of this, set `PYTHONUTF8=1` (a Windows text-encoding problem in
`voice_service/service.py`); `run.py` does that for you.

## The 3D teachers

The female and male teachers are `frontend/public/avatars/teacher.glb` and `teacher-male.glb`. They follow the **Teacher
voice** dropdown. Their authors are credited in `frontend/public/avatars/CREDITS.md`. If the files are missing, the 2D
cartoon teacher is shown.

## Check it in a browser: `tools/qa/`

```sh
pip install aiohttp
python tools/qa/check_teacher.py --male --reach     # renders, speaks, pauses, gestures, voice switch, arm reach
python tools/qa/measure_lecture.py --store tools/dev_demo/lectures/<engine>   # compiled versus live timing
```

They use a headless browser with software 3D, so no GPU is needed. See each script's header for what it reports.

## Files

| File | Purpose |
|---|---|
| `run.py` | Starts the voice server and the frontend together. |
| `serve.py` | The voice server for the demo lesson: stand-in voice plus `voice_service.lecture.CompilingNarrator`. |
| `windows_voice.py`, `edge_voice.py` | The two stand-in voices. |
| `requirements.txt` | Extra packages for the `edge` voice only. |
