# Teacher avatar — Track B

Public API from this folder's `index.ts`: `TeacherAvatar`, `TeacherAvatar2D`, and the
`AvatarPhase` / `AvatarVoiceSink` types.

**The default teacher is the 3D one**, and it follows the selected voice: `public/avatars/teacher.glb` for a
female voice, `public/avatars/teacher-male.glb` for a male voice (voice ids `af_*` / `am_*`); if that file is missing or cannot load, the
2D cartoon is shown instead. `NEXT_PUBLIC_EDAPTIVE_3D_AVATAR=0` forces the 2D one, and `?avatar=<name>` in the URL
tries another GLB from `public/avatars`.

## Pacing and gestures
Every sentence is separated by a 1 s gap (`SENTENCE_GAP_MS` in the voice feature), and the mouth stays shut
in the gaps and in the padding TTS puts around sentences. `gestures.ts` picks gestures from the lesson part type and the sentence text (opening gesture, text cues, rotating
beats, a second gesture on long sentences; mouth-closed gestures only); `avatar-voice.ts` fires it on the audio clock. The 3D camera defaults to
`mid` (waist-up) so hands are in frame; `upper` and `head` hide them.

When the server sends a `lecture` frame (a part compiled ahead of time, `voice_service/lecture.py`), the avatar plays
its saved speech timings and gesture plan as they are; without one it works them out live. `gestures.mjs` is plain
JavaScript so Node can run the same rules when a lecture is compiled.

Full guide, including how to run it with the Kokoro voice on Apple Silicon: `docs/voice/TEACHER_AVATAR.md`.
To make a rigged GLB loadable: `tools/prepare_avatar_glb.py`.

`window.__gestures` and `window.__audio` are test hooks: sentences and gestures are pushed to them only if a test
has created those arrays first. They do nothing otherwise.

## 3D teacher (`TeacherAvatar`)

Uses [TalkingHead](https://github.com/met4citizen/TalkingHead) (MIT, `@met4citizen/talkinghead`
1.7.0) on `three` (MIT). Runs in the browser on WebGL: no GPU requirement, no hosted service,
offline. It gives one avatar with word-driven mouth sync, blinking, eye contact and idle motion.

How sound and mouth stay together: `LiveNarrator` accepts an optional `NarrationSink`. When the 3D
teacher is ready, `TeacherAvatar` hands `LessonPlayer` an `AvatarVoice` sink; the narrator then goes
silent (it still keeps time for captions and completion) and forwards each sentence's PCM to
`AvatarVoice`, which sends it to TalkingHead's streaming mode (`streamStart` / `streamAudio` /
`streamNotifyEnd`) with word timings spread over the sentence's length. Replay, navigation and a new
message call `stop()` (`streamInterrupt` + `stopSpeaking`), so the queue is cleared and the mouth
closes. Pause and resume suspend and resume TalkingHead's audio clock and animation together.

If the 3D teacher is off, or WebGL or the model is unavailable, `TeacherAvatar2D` is shown and the narrator plays the sound
itself, as before. The TTS call stays behind the narration stream (`/voice-preview-api/narrate`),
so swapping the voice engine does not touch avatar code.

### Changing the teacher
Drop another GLB at `frontend/public/avatars/teacher.glb`. It needs a Mixamo-compatible rig plus the
52 ARKit and 15 Oculus viseme (`viseme_*`) blendshapes (TalkingHead README, Appendix A).
The sample is TalkingHead's `brunette.glb`, made at Ready Player Me, licensed **CC BY-NC 4.0**
(non-commercial). Replace it before any commercial use.

### Build note
TalkingHead loads lip-sync files with a runtime-built `import()`, which Turbopack cannot bundle.
`frontend/build-tools/talkinghead-loader.cjs` (wired in `next.config.ts`) marks it as a runtime
import; that path is never reached because `TeacherAvatar` registers English lip-sync itself.
Re-check this when upgrading TalkingHead.

## 2D teacher (`TeacherAvatar2D`)
A cartoon (`frontend/public/avatar/teacher.webp`, transparent) whose mouth follows the audio level
from the `analyser` that `LiveNarrator` exposes. No audio or network work of its own.

Both respect `prefers-reduced-motion` where they animate on their own.
