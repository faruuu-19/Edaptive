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

Frontend implementation follows the installed Next.js route-handler and client-component guides. Cross-feature imports use public `index.ts` exports. Existing household/profile screens are unchanged. Subject-to-voice assignments remain pending; this review screen offers both candidates.

## Timed class demo

Open `http://127.0.0.1:3001/timetable-demo` after starting the same services. Choose a custom Pakistan class time or click Quick demo for a class in 30 seconds. Preparation, due-time alarm, Start class and Borrow 5 minutes are documented in `docs/voice/TIMETABLE_FLOW.md`. The original manual `/lesson-preview` remains available when no timetable preparation is running. The service uses `--content-root` (default: the sibling assessment-card-generator workspace) for the audited catalog and existing script agent.
