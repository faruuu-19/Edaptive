# Teacher avatar in scheduled lesson delivery

The shared `frontend/src/features/lesson-player/LessonPlayer.tsx` now renders the talking teacher for both normal scheduled classes and existing preview/demo routes. The timetable still owns joining, saved lesson positions, finishing, exit, and rejoin. No backend, scheduling, consent, grading, or mastery policy changed.

## Source and extracted scope

PR [#19](https://github.com/faruuu-19/Edaptive/pull/19) provides a portable demo server and launcher. It contains no avatar implementation. The avatar was extracted from the separate `track-b/teacher-avatar-snapshot` branch, commit `9de6a4b411c3e8a4ee232397c9f646f68e18ba73`.

Included: the 3D and 2D teachers, both local GLBs, artwork and credits, gesture planner, voice sink, and TalkingHead bundling fix. Only the required narration/frontend changes were adapted. The snapshot's compiled-lecture backend, Windows voice engine, standalone launcher, and older lesson/class logic were not copied.

The 3D packages are pinned and locked in the existing frontend package files. Install with `npm ci` in `frontend`, then start the regular local system as documented in `docs/RUN_CURRENT_SYSTEM.md`. Click Maths, then join the scheduled class as usual. The teacher automatically appears beside the lesson content. `/lesson-preview` remains the existing manual-review route when the operator has enabled it.

## Playback and fallback

- The teacher follows the voice selector: female `af_heart`, male `am_michael`.
- Avatar audio initialization must succeed before it takes over narration. A failed audio worklet falls back to ordinary narration and the 2D teacher.
- Captions, gestures, and lesson completion follow the avatar's real playback clock. Receiving the network `done` frame alone never completes a lesson. Temporary audio underruns do not finish a class.
- Pause freezes the audio clock. Replay, navigation, voice changes, and exit cancel stale playback and callbacks. Switching models after pausing restarts rendering.
- A one-second pause separates sentences; additional chunks from one Kokoro sentence do not receive extra pauses or repeated captions. Mouth timing excludes quiet padding, and fully silent audio gets no mouth movements.
- Missing models or unavailable WebGL use the original 2D teacher. `NEXT_PUBLIC_EDAPTIVE_3D_AVATAR=0` can force that display at frontend startup/build time.
- Existing optional compiled-timeline frames are understood, but no new backend cache or compilation service is required.

The teacher uses no external runtime services, camera, microphone, or stored child media. Models have no Draco compression, and the decoder path is explicitly local. Preserve `frontend/public/avatars/CREDITS.md`: the source branch records the model creators and states that their redistribution licences remain unconfirmed.

## Verification

From `frontend`:

```sh
npm run test:avatar
npm run typecheck
npm run lint
npm run build
```

The Node tests exercise the real narrator and avatar adapter with deterministic audio/head substitutes. They cover scheduled completion after actual playback, a single audible source, worklet fallback, cancellation, split sentences, silence, pause-clock captions, delayed end frames, and lip-sync recovery after an underrun. They require no browser, voice model, student session, or database.

Browser verification uses the existing saved lesson preview, which does not write student progress. It cannot substitute for a complete scheduled class rehearsal at the configured class time. Word timings within a sentence are estimated; a full scheduled end-to-end class should still be rehearsed before a student demonstration.
