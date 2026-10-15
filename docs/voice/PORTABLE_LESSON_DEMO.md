# Portable lesson demo (Windows, macOS, Linux)

This runs the same `/lesson-demo` page as the full system, for people who only need the
lesson screen, for example to build the avatar. It needs **Node.js and Python only**: no
Apple silicon, Kokoro/MLX, Ollama, Qwen, Postgres or backend.

It plays one saved, checked draft lesson (Grade 2 Module 1 Lesson 1, 19 parts). It cannot
prepare lessons, grade answers or record anything. The content is draft and is not approved
for children.

## For the person building on it (any computer)

1. Install Node.js 20.9 or newer and Python 3.9 or newer.
2. In the repository's `frontend` folder, run `npm install` once.
3. From the repository root:

   ```sh
   python tools/run_lesson_demo.py            # Windows
   python3 tools/run_lesson_demo.py           # macOS / Linux
   ```

   With a narration recording (see below), add `--audio-dir <folder>`.
4. Open `http://127.0.0.1:3001/lesson-demo` and press **Listen**. Press Ctrl+C in the
   terminal to stop both programs.

Other options: `--web-port`, `--voice-port` (if a port is busy), and `--script` (another
saved `script-0.1` draft).

### What you hear

- **Without a recording:** silence, timed to the number of words in each sentence. The page,
  sentence highlighting, pause/resume, replay, questions and automatic advancing all behave
  as in the real system, so layout and animation timing can be built. Lip-sync to real speech
  cannot be judged.
- **With a recording:** the real Kokoro voices, both teachers. Audio frames use the same
  format as the live service, so the avatar sees exactly what it will see in production.

## Where the avatar plugs in

The lesson player is `frontend/src/features/lesson-player/LessonPlayer.tsx`. It reads the
voice through `LiveNarrator` (`frontend/src/features/voice/live-narrator.ts`), which
schedules each sentence on the browser audio clock and reports:

- `onPlaying`: the first sentence of a part started;
- `onCaption(index)`: which sentence is being spoken now;
- `onComplete`: the part finished.

The player turns these into phases (`ready`, `preparing`, `playing`, `paused`, `complete`).
Per `AGENTS.md`, avatar code goes in `frontend/src/features/avatar/` (Track B) and other
features import it only through its `index.ts`. Drive the avatar from the player's phase and
current caption, and from the narrator's audio clock when mouth movement needs it. Do not
change the voice service or the narration frame format without agreeing it with Track B.

## For the person with the Mac (record the narration once)

Do this on the Apple silicon Mac that already has the voice set up (`docs/RUN_CURRENT_SYSTEM.md`),
from the repository root, with the existing voice Python environment:

```sh
~/edaptive-voice/venv/bin/python -m voice_service.record_demo_audio --out ~/edaptive-voice/demo-audio
```

It generates every main-path sentence for both teacher voices (a few minutes) and writes
`manifest.json` and `<voice>/<segment>.ndjson`. Zip that folder and send it privately.
**Do not commit it**: audio is never stored in the repository (`/demo-audio/` and `*.wav` are
ignored). The person on Windows unzips it anywhere and passes the folder with `--audio-dir`.

Safety checks built into replay:

- each recorded sentence carries a hash of its text; if the script is edited later, that
  sentence plays silent timing instead of stale audio;
- a damaged, truncated or mismatched file is ignored, never played;
- at start the demo prints how many segments have recordings for each voice.

## Verification and limits

- `make check` includes `voice_service/test_demo_server.py` (replay, fallback, damaged files,
  path safety, the real HTTP handler) and `tests/test_run_lesson_demo.py` (launcher).
- Checked on macOS with a Python that has no MLX: the page loaded, played, highlighted
  sentences and advanced to later parts on silent timing.
- **Not checked:** running on Windows itself (the launcher ends the `npm` process tree with
  `taskkill` there; report any problem), and the recorder against the real Kokoro model.
- The real timetable, alarm, parent and scheduled-class pages need the backend and are not
  part of this demo.
