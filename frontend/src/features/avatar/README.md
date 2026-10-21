# Teacher avatar — Track B

Public API: `TeacherAvatar`, `TeacherAvatar2D`, `AvatarPhase`, and `AvatarVoiceSink`, exported from `index.ts`.

Extracted from `track-b/teacher-avatar-snapshot` at `9de6a4b411c3e8a4ee232397c9f646f68e18ba73` and integrated into the shared scheduled/preview lesson player. PR #19 contains the portable demo launcher, rather than these avatar files.

The default 3D teacher uses bundled TalkingHead 1.7.0 and Three.js 0.180.0. Models are local: `public/avatars/teacher.glb` (female) and `teacher-male.glb` (male). The selected teacher voice determines the model. `NEXT_PUBLIC_EDAPTIVE_3D_AVATAR=0` forces the 2D teacher. For local model testing, `?avatar=<name>` selects a GLB from `public/avatars`; `?view=full|mid|upper|head` selects the camera. The default `mid` view includes hand gestures.

`AvatarVoice.prepare` initializes streaming before taking over narration. Its real AudioContext clock drives captions and gestures; stream-end callbacks drive lesson completion. `pause`, `resume`, and `stop` cover paused classes, replay, navigation, voice changes, and leaving class. Silence has no word timings, so the mouth stays shut. Word timing within spoken sentences remains an estimate.

`TeacherAvatar2D` follows the ordinary narrator's analyser and uses `public/avatar/teacher.webp`. It is used when WebGL, the model, or the streaming audio worklet is unavailable. Both teachers run locally; no learner camera or microphone is needed.

TalkingHead's dynamic lip-sync import needs the small Turbopack loader in `build-tools/`. The app registers bundled English lip-sync explicitly. Both GLBs are uncompressed, and the library's external Draco decoder default is overridden with a local path.

Source artwork credits and model licence status are preserved in `public/avatars/CREDITS.md`. See the repository's `docs/voice/TEACHER_AVATAR_INTEGRATION.md` for setup and verification. Optional `window.__audio` / `window.__gestures` arrays are development hooks, populated only if a test creates them first.
