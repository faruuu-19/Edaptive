# Local lesson voice preview — Track B / Amna

Generates Kokoro speech live, sentence by sentence, for one explicitly supplied script-agent draft. Audio is streamed as PCM in NDJSON and stays in browser memory. Nothing is recorded to the session log or saved as audio. No microphone, cloning, cloud API, avatar or widget is used.

This is an **opt-in review preview**, not the authenticated student delivery API. It must not be presented as production delivery or record mastery. The underlying cards are drafts, and maths verification of script text does not verify synthesized audio. Only the main path is exposed; conditional hints/answers need the assessment runtime before integration.

## Start

Use the existing isolated Python 3.12 voice environment, outside this repo. MLX-Audio 0.5.8 and MLX 0.32.3 are installed there; the existing Kokoro model and presets are reused without downloads.

From the team repo root:

```sh
HF_HUB_OFFLINE=1 ~/edaptive-voice/venv/bin/python -B -m voice_service.service \
  --script "$HOME/Downloads/edaptive-assessment-card-generator/artifacts/script-agent/qwen9b-grade2-m1-l1/math_g2_m1_l1_pairs_to_ten.script.json"
```

The voice service binds to 127.0.0.1:8766 and warms the model before accepting requests. In another terminal, from `frontend/`:

```sh
EDAPTIVE_VOICE_PREVIEW=1 NEXT_TELEMETRY_DISABLED=1 npm run dev -- --hostname 127.0.0.1 --port 3001
```

Open `http://127.0.0.1:3001/lesson-preview`. Click Listen to enable browser audio. Pause/resume freezes the playback clock; replay, navigation and voice changes cancel old requests. At questions and reflections the player waits for Continue; ordinary explanations advance automatically. Picture directions appear as text captions, not as spoken instructions.

The preview page and proxy return 404 unless `EDAPTIVE_VOICE_PREVIEW=1`. The service accepts only known main-path segment IDs and the installed `af_heart` / `am_michael` presets, not arbitrary submitted text or uploaded audio. It serializes model access and rejects concurrent requests. Stop both processes to end the preview. The local loopback service is not a replacement for household authentication.

## Checks

```sh
~/edaptive-voice/venv/bin/python -B -m unittest voice_service.test_service
cd frontend
npm run lint
npm run build
```

Speech preparation is copied byte-for-byte from Amna's tested `voice_module/speech_prep.py`; keep its existing regression tests when moving it into a formal shared package. No assessment or script-agent implementation changes are required.

Frontend implementation follows the installed Next.js route-handler and client-component guides. Cross-feature imports use public `index.ts` exports. The household/profile theme is retained; Maths opens the day plan and parent child rows open their dashboards. Subject-to-voice assignments remain pending; this review screen offers both candidates.

## Scheduled classes

Open `http://127.0.0.1:3001/timetable` after starting the services (`tools/run_local_application.py`). A parent saves only the daily school start time. The system builds the timetable and prepares the next required Maths lesson from its concept and assessment cards; at class time the child joins or snoozes five minutes. There is no shortcut that skips preparation or rechecks an older saved script. Full flow, memory behaviour and verification status: `docs/voice/TIMETABLE_FLOW.md`. The manual `/lesson-preview` remains available for reviewing one saved script. The service uses `--content-root` (default: the sibling assessment-card-generator workspace) for the audited catalog and the existing script agent.

The isolated `/lesson-demo` uses an existing ready job selected by the launcher or `--demo-job-id`. It has no main-screen button, never submits generation, and does not record student progress. See `docs/voice/DAILY_TIMETABLE.md` for the four-class plan and persisted curriculum state.


Current packaging: follow `docs/RUN_CURRENT_SYSTEM.md`. Content defaults to this
repository, `docs/content/lesson-pairs.json` is hash-checked, and the script agent
is bundled. The external Downloads workspace is no longer required. The original
setup examples above describe the earlier operator environment.

## Compiled lectures (no waiting at class time)

By default every sentence is spoken by the voice model while the child waits ("The teacher is getting ready to
speak"). `voice_service/lecture.py` records the narration ahead of time instead. For each part of a lesson and each
voice it saves one timeline: the audio, where she is really speaking inside each sentence, the 1 s pause between
sentences, and the gestures that go with the words, all on one clock. Playing a compiled part is just reading it
back, so it starts at once and always plays exactly the same way (docs/voice/TEACHER_AVATAR.md).

- **When it is built.** `PreparationJobs` calls the recorder right after a lesson becomes ready, while the voice is
  loaded and no class is waiting. The lesson is already `ready` and no longer `running`, so a class that starts
  meanwhile does not pause it; the recorder stops within one sentence when a class reserves the voice, and keeps
  what it finished. Anything not recorded yet is recorded the first time it is spoken (the child hears it live, as
  before, and the next play is instant).
- **Where it is kept.** `<job store>/lectures/<engine>/<voice>/<part>-<hash>.json` (timeline) and `.pcm` (raw 16-bit
  mono audio). The hash covers the voice engine, the voice, the part id and its exact text, so an edited script
  never plays old audio; a damaged file is ignored and spoken live. Roughly 0.5 MB per part per voice. Least recently
  used parts are removed above `--lecture-max-gb` (default 4). It holds teacher audio and lesson text only.
- **Flags.** `--lecture-store DIR`, `--lecture-max-gb N`, `--no-lecture-cache` (speak live, as before).
- **What the browser receives.** The same NDJSON stream as before, with one extra `lecture` frame after `start`:
  `{"type":"lecture","gap_ms":1000,"sentences":[{"utterance","speech_start_ms","speech_end_ms"}],"gestures":[{"at_ms","name","seconds","mirror"}]}`.
  An older frontend ignores it; a part with no `lecture` frame is planned live.
- **Gestures** are planned by the same JavaScript the browser uses (`frontend/src/features/avatar/gestures.mjs`),
  run under Node by `tools/plan_gestures.mjs`. Without Node the audio is still compiled and the browser plans
  gestures live.
- **Tests:** `python -m unittest voice_service.test_lecture`.
