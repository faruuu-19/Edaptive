# The teacher avatar: pacing, gestures and how to run it (Apple Silicon / Kokoro)

Track B. Written for whoever runs the full local system with the real Kokoro voice (the Apple Silicon
Mac setup in `docs/RUN_CURRENT_SYSTEM.md`) and wants the same teacher behaviour that was built and tested
on a Windows PC. Nothing here changes the voice service or the Kokoro model.

## What you get

1. **A 1 second pause between every sentence.** The sound is silent in the gaps and the avatar's mouth is
   shut, both in the gaps and in the quiet padding TTS puts around each sentence.
2. **Gestures that go with what she says**, chosen from the lesson part type and from the sentence text:
   a wave to begin, pointing for "look" and "careful", a thinking pose for questions, thumbs up for praise,
   a shrug for "maybe", a warm smile for encouragement, an open hand for "now it's your turn", and so on.
3. **Compiled lectures: nothing to prepare at class time.** The narration, the pauses, where she is really speaking in
   each sentence and the gestures are recorded ahead of class on one timeline, so a part starts almost at once
   (see "Compiled lectures" below).
4. **A 3D teacher** (TalkingHead, runs in the browser) with blinking, eye contact and idle motion, or the
   2D cartoon teacher when the 3D one is off or cannot load.

Pacing and gestures live in the frontend, so they apply to **any** voice engine: Kokoro on your Mac, the
Edge/Windows voices used on the PC, or whatever replaces them. You do not need to change the voice service.

## Run it on your Mac

Start the system exactly as in `docs/RUN_CURRENT_SYSTEM.md`:

```sh
make setup            # picks up the two new npm packages (three, @met4citizen/talkinghead)
python3 tools/run_local_application.py --allow-draft-lessons
```

The lesson player (and so the teacher) is on `/lesson-preview`, `/lesson-demo` and the scheduled class
pages. The **3D teacher is the default**: it loads `frontend/public/avatars/teacher.glb` (see "The 3D model" below)
and falls back to the 2D cartoon teacher if that file is missing or cannot load. So:

- put your rigged models in `frontend/public/avatars/`: `teacher.glb` for the female teacher and `teacher-male.glb` for
  the male one. The teacher follows the **Teacher voice** dropdown (voice ids like `af_heart` are female, `am_michael`
  is male: the second letter is the gender), and a "Changing teacher…" note shows while the other model loads;
- to try one file for both voices, open any lesson page with `?avatar=<name>` (a file in `public/avatars`,
  without `.glb`);
- to force the 2D teacher, start the frontend with `NEXT_PUBLIC_EDAPTIVE_3D_AVATAR=0`.

The stage is wide (460 x 427 px) and the camera sits a little back so an outstretched arm stays in frame.
Camera: `?view=mid` (waist-up, the default for 3D), `full`, `upper` or `head`. **Use `mid` or `full` if you
want to see gestures**: hands are out of frame in `upper` and `head`.

Example: `http://127.0.0.1:3001/lesson-demo?avatar=teacher&view=mid`

## Compiled lectures (no "getting ready" at class time)

Without this, every sentence is spoken by Kokoro while the child waits. `voice_service/lecture.py` records each part
of a lesson once per voice: the audio, the speech start and end inside each sentence, the 1 s pause, and the full
gesture plan, all in milliseconds on one clock. Playing it back is just reading a file. **This is on by default in
`voice_service.service`; there is nothing to switch on.** Details and flags: `voice_service/README.md`.

What happens on your Mac:

1. A lesson finishes preparing (`PreparationJobs.run`): the script is validated and the voice is warmed. The job
   becomes `ready` **first**, then `record_lecture` compiles every part for both voices (`af_heart`, `am_michael`),
   using the loaded Kokoro model. The job shows `lecture_done` / `lecture_total` while it works.
2. A class starting meanwhile is never blocked: the job is already `ready` and no longer `running`, so `reserve()`
   does not pause it; the recorder checks between sentences and stops within one sentence's synthesis. What it did
   finish is kept; the rest is compiled the first time it is spoken (spoken live, saved at the end).
3. At class time `/narrate` finds the compiled part and streams it immediately, with one extra `lecture` frame holding
   the saved timeline. The avatar plays that timeline as saved (speech timings, gestures); the audio, gaps and gestures
   cannot drift apart because they were computed together.
4. Edit a script and the hash changes, so old audio is never played; a damaged file is ignored and spoken live.

Measured on the PC (Edge neural voices as a stand-in for Kokoro; headless browser with software 3D):

| | first sound after the request | click to speaking |
|---|---|---|
| spoken live | about 1.6 to 4 s | 3.9 s |
| compiled | 79 ms average, 348 ms worst, over all 38 parts | 0.7 to 1.2 s |

Compiling the whole 19-part demo lesson for both voices took 190 s and 21 MB. Kokoro on a Mac will differ in speed;
please check yours: the job's `lecture_done` should reach `lecture_total`, and the first sound of a compiled part
should be near-instant. Compiled lectures live in `<job store>/lectures/kokoro-82m-bf16/`. To start clean, delete that
folder. `--no-lecture-cache` turns the feature off.

**The gesture plan is computed by Node.** `tools/plan_gestures.mjs` runs `frontend/src/features/avatar/gestures.mjs`,
the same file the browser uses, so there is one set of rules. Node is needed on the machine that runs the voice
service (it is already needed for the frontend). If `node` is not on the PATH the audio is still compiled and the
browser plans gestures live. Tests: `python -m unittest voice_service.test_lecture` (the Node tests are skipped
without Node).

**Kokoro splitting a sentence.** If Kokoro returns several audio chunks for one sentence they share an `utterance`
number. The compiler merges them into one sentence. For a part that is spoken live, the player treats chunks of one
sentence as one sentence: no 1 s pause is inserted in the middle of a sentence.

## What to check with Kokoro

Kokoro frames differ from the PC voices (24 kHz, `ready_after_s`), so please confirm on your machine:

1. Press **Listen**. There is a clear ~1 s silence between sentences (about 1.4 s in practice: the 1 s gap
   plus Kokoro's own padding), and her mouth stays shut during it.
2. A wave on the opening sentence of the first part; a thinking pose on questions; pointing on "look" / "careful".
3. **Pause** freezes the sound, the mouth and the gestures together; **Keep listening** resumes in step.
4. **Replay this part** and **Next** restart cleanly (new opening gesture, no sound left over from before).
5. The browser console has no red errors.

If the mouth moves while it should be shut, check that Kokoro's silence is quiet enough: leading and trailing
silence is detected as audio below about 2% of full scale (`SILENCE_LEVEL` in
`frontend/src/features/avatar/avatar-voice.ts`). Raise it if Kokoro's padding has a faint noise floor.

## How it works (so you can change it)

| What | Where |
|---|---|
| 1 s gap between sentences: `SENTENCE_GAP_MS` | `frontend/src/features/voice/live-narrator.ts` |
| Sends each sentence's audio to the avatar (`NarrationSink`) | same file |
| Word timing over the spoken part only, silent gap audio, gestures on the audio clock | `frontend/src/features/avatar/avatar-voice.ts` |
| Which gesture goes with which part type and sentence | `frontend/src/features/avatar/gestures.ts` |
| 3D loading, camera, fallback to 2D, the fixed standing pose (`STANCE`) | `frontend/src/features/avatar/TeacherAvatar.tsx` |
| The 2D teacher | `frontend/src/features/avatar/TeacherAvatar2D.tsx` |

- **The gap.** `LiveNarrator` never schedules a sentence closer than `SENTENCE_GAP_MS` to the one before. When
  the 3D teacher plays the sound, `LiveNarrator` goes silent (it still keeps time for captions) and passes each
  sentence to `AvatarVoice`, which sends 1 s of real silence to TalkingHead between sentences.
- **The shut mouth.** TalkingHead moves the mouth only for words it is given times for. Word times cover only
  the part of each sentence where she is really speaking (leading and trailing silence trimmed), so there is no
  mouth movement in the gaps. The 2D teacher's mouth follows the audio level, so it closes by itself.
- **Gestures** are planned sentence by sentence as the audio arrives (`GesturePlanner` in `gestures.ts`):
  1. the first sentence of a part gets that part type's opening gesture (they take turns, so it varies);
  2. otherwise a sentence matching a text cue (look, careful, a question, praise, "now", ...) gets that cue's gesture;
  3. otherwise most sentences get a rotating "beat" gesture, so she keeps moving naturally (every 4th cue-less
     sentence is left still);
  4. a long sentence (`LONG_SENTENCE_MS`, 4.5 s) gets a second gesture around its middle.

  Gestures are never closer than 2.5 s apart (`MIN_SPACING_MS`), never repeat the one just used, skip very short
  sentences (`MIN_SENTENCE_MS`), and the two hands alternate. On the Grade 2 "Pairs to ten" lesson this gives
  about one gesture per sentence (88 over 86 sentences). Gestures fire on the avatar's audio clock, so they stay in
  step with the speech and stop while paused. **Only gestures that keep the mouth closed are used**: TalkingHead's
  grin, big grin, wink and surprised faces open the jaw, which would open her mouth in the 1 s gaps.
- **A steady stance.** By default TalkingHead picks a new random pose every 5 to 30 s (hand on hip, wide stance,
  turned). That looks like posing, so `TeacherAvatar` holds one relaxed standing pose (`STANCE = "side"`: arms down)
  by playing it with a very long duration, which postpones every idle pose change. Other names: `straight`
  (symmetrical, stiffer), `hip`, `wide`, `turn`. Blinking, eye contact and small head movement stay on.
- **TalkingHead's own gestures:** `handup`, `index`, `ok`, `thumbup`, `thumbdown`, `side`, `shrug`, `namaste`, plus
  emoji animations (face expressions, some with a hand). To add a rule, add a line to `RULES` or `OPENERS` in
  `gestures.ts`. Gestures are generic: there is no counting on fingers or pointing at a specific number.

## The 3D model

`teacher.glb` and `teacher-male.glb` must each be a rigged full-body GLB with:

- a Mixamo-compatible skeleton (Hips, Spine, Neck, Head, LeftEye, RightEye, arms, hands, legs);
- the 52 ARKit blendshapes and the 15 mouth-sound shapes (`viseme_sil`, `viseme_PP`, `viseme_FF`, ... `viseme_U`);
- blendshape **names** stored in `mesh.extras.targetNames`, and the root object named `Armature`.

Some exporters (Babylon.js, for one) write the names somewhere else and leave out a few ARKit shapes. Repair a
copy with the included script (Python standard library only):

```sh
python3 tools/prepare_avatar_glb.py "My Teacher.glb" frontend/public/avatars/teacher.glb
```

It reports what it changed, and stops with a clear message if the skeleton or the mouth-sound shapes are
missing (those cannot be invented). Tested on the PC: the female model ("Teacher Female Narration 01", a Babylon.js
export) needed names copied, 9 empty gaze and tongue shapes added and the root renamed; the male model (`mechar.glb`,
a Blender export) already had names and an `Armature` root and only needed the 9 empty shapes.

**Models and credits.** This branch includes the two teachers, `teacher.glb` (female, by **LasquetiSpice**) and
`teacher-male.glb` (male, by **pendekaralahmad**), so pulling it gives you a working 3D teacher. They are credited in
`frontend/public/avatars/CREDITS.md`. **Their licence terms are not yet confirmed**: check them at the source before any
wider or commercial distribution. TalkingHead's own sample avatars are placeholders, not for students, and most are
non-commercial (Ready Player Me `brunette.glb` is CC BY-NC 4.0). Check the licence of any model you use.

## Known limits (verified on the PC, please re-check on the Mac)

- Eye gaze: the model had no eye-direction shapes; empty ones were added, so the eyes blink and the head moves
  but the eyeballs do not track side to side.
- Mouth movement on that model is fairly subtle.
- Gestures are checked in a headless browser with software 3D, not on a real GPU.
- Word timings inside a sentence are estimated from word length, not read from the TTS.
- TalkingHead's `import()` of its lip-sync files cannot be bundled by Turbopack. `frontend/build-tools/talkinghead-loader.cjs`
  (wired in `frontend/next.config.ts`) marks it as a runtime import. Re-check this when upgrading TalkingHead.
- The old browser tab can show "Getting the lesson ready…" forever after the dev server restarts. Hard refresh
  (Ctrl/Cmd+Shift+R).

## Files changed by this work

(Compiled lectures: new `voice_service/lecture.py`, `voice_service/test_lecture.py`, `tools/plan_gestures.mjs`; small
changes to `voice_service/service.py` and `jobs.py`, `frontend/src/features/voice/live-narrator.ts` and
`avatar-voice.ts`; `gestures.ts` became the plain-JavaScript `gestures.mjs` so Node can run it.)

New: `frontend/src/features/avatar/` (3D and 2D teacher, gestures, voice sink), `frontend/build-tools/`,
`tools/prepare_avatar_glb.py`, this guide. Changed: `frontend/src/features/voice/` (gap, narration sink),
`frontend/src/features/lesson-player/` (teacher in the layout, part type passed to the avatar),
`frontend/next.config.ts`, `frontend/package.json` and lockfile, `.github/CODEOWNERS`.