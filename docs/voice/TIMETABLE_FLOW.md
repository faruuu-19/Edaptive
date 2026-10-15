# Timetable, advance preparation and live class — Amna / Track B

How a scheduled class works end to end. All of it is local and offline: no cloud model, no paid API, no stored student audio.
Every card is still a **draft**. Draft lessons require the operator-only local evaluation setting `EDAPTIVE_ALLOW_DRAFT_LESSONS=1`; the parent form has no draft switch. The player identifies draft content. This setting does not approve content for children.
The source of truth for matched content is the audited inventory in `docs/voice/PAIR_INVENTORY.md` (93 three-level draft pairs: 91 published, 2 supplementary Grade 3 review pairs). No pair is approved for child delivery.

## Where things live

| Piece | Location | Persistence |
|---|---|---|
| Daily start-time preference | `backend/app/modules/lesson_delivery/routines.py` (`lesson_school_routine`) | survives restarts |
| Timetable, slots, class phase, saved lesson position | `backend/app/modules/lesson_delivery/` (Postgres table `lesson_timetable`) | survives restarts |
| Preparation jobs (progress, checkpoints, ready script) | `voice_service/jobs.py` (SQLite at `~/edaptive-voice/jobs/`) | survives restarts |
| Script generation | `voice_service/preparation_worker.py` → existing script agent + local Qwen | checkpoint per job |
| Teacher voice | `voice_service/service.py` (Kokoro, loopback only) | in memory only |
| Screens | `/timetable` (`frontend/src/features/lesson-player/Timetable.tsx`) | — |

`/timetable-demo` redirects to `/timetable`. The isolated prepared review lecture is `/lesson-demo`, with no main-screen link.

## Flow

1. **Daily time.** A parent saves only the child's daily school start time in Pakistan time. No date, module, lesson, break or preparation control is exposed, and the API rejects these overrides. The system chooses the next required matched Maths lesson in curriculum order for the child's grade and assigns today (if the time is still ahead) or the next school day. It estimates the preparation lead time itself. After delivery it plans the following day, without counting delivery as mastery. An unattended prior-day lesson moves to the next school time with its ready script preserved. A new time moves an upcoming class; a class in progress keeps its current time. The day contains Maths, Science, English and Physical class with system-owned breaks. Science, English and Physical class reserve 20-minute Coming soon slots and remain inactive. Unprepared Maths reserves 20 minutes including its buffer, then uses the prepared script estimate. See DAILY_TIMETABLE.md for strict gap handling and persistent delivery progress. Progress, evaluations, consent, placement and adaptive sequencing are separate modules.
2. **Prepare.** From `start − lead time` a backend worker submits a job to the voice service. The worker runs the script agent with the installed `qwen3.5:9b-q4_K_M`, one script section at a time. Progress is `completed sections / total` plus planning, validation and voice warm-up, never a timer. A memory guard pauses (not fails) the job when swap grows past 512 MiB or pressure turns critical, and the job resumes from its checkpoint.
3. **Validate.** Flagged sections get up to two repair rounds. A script that still has flags is not marked ready, and Start stays disabled.
4. **Duration.** Estimated from the prepared script (narration, thinking pauses, assessment response time plus a buffer), clamped to 15–35 minutes, with the basis shown. If a lesson overruns, later slots move and the break length is kept.
5. **Alarm.** At class time the open browser tab rings and offers **Join class** or **Snooze 5 minutes**. Start is refused by the server unless the time has come *and* preparation is ready.
6. **Borrow.** Moves this class and every later slot five minutes; breaks keep their length; finished preparation is kept. A class can be snoozed **once**; the server refuses a second snooze and the button is no longer shown.
7. **Class.** Start creates a real session (`session.started`), reserves the voice, and narrates the main path through live Kokoro. The child can pause, resume and replay. Reflection and question sections wait for Continue; at this stage questions are spoken with thinking pauses only. There is no answer submission, grading, hint or follow-up.
8. **Finish / cancel.** Finish is accepted only after the last part has been narrated. Both `finish` and `cancel` release the voice, which unloads Kokoro to free memory. An unattended class (no heartbeat for 90 s) releases it the same way; its saved position is kept in the timetable.
9. **Child screens.** The child's home shows the subjects (the Maths tile has a small preparation bar and percentage) and, below them, today's timetable: what and when, with no preparation or planning detail. Tapping Maths shows "A day of learning" and a single card ("It's time for Maths!", or the start time before then) with no timetable. The parent view keeps the detailed plan.

## Memory behaviour

Qwen and Kokoro are never both loaded for long. Kokoro releases its weights while Qwen prepares. A preparation for a later lesson **yields** to a class that is starting: it is paused, and it resumes from its checkpoint once the class releases the voice. (Until 2026-10-13 a yielded job stayed paused forever; this is now covered by `voice_service/test_jobs.py`.) Because the voice may be unloaded between classes, Start allows up to 60 s to reload it.

## Events

Existing identity/session events remain unchanged. `lesson.delivery_changed` adds a versioned payload for start, snooze, position, finish and explicit cancellation; it is registered through a separate contract PR before the feature merge. The UI calls snooze; its existing payload action is `borrow`. Heartbeats do not create session-log events. Further voice/replay event proposals remain in `docs/voice/EVENTS_PROPOSAL.md`.

## Verification status

- Backend tests (run against the isolated QA database, never the household's), voice-service tests, script-agent tests, frontend lint, typecheck and build pass.
- A fresh local Qwen script and all 19 main-path Kokoro sections were exercised in the isolated QA flow; the current prepared demo also produced real audio through its HTTP proxy. The latest UI additions have passed frontend lint, typecheck and build; they have not all been visually checked by browser automation.
- Heuristic checks on the script (numbers, equations, coverage, leakage) do not prove pedagogical quality. Human review is still required.
- The browser alarm needs an open tab and one click to enable sound. It is not an OS alarm or push notification.

## Local start-up

From the repository root, with the existing isolated Python runtimes, database and downloaded models:

```sh
PATH="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" \
  python3 tools/run_local_application.py --allow-draft-lessons
```

Open `http://127.0.0.1:3001/` for Ibrahim's original profile picker and child home. The existing Maths tile opens lesson delivery. In the parent area, clicking a child profile opens that child’s dashboard. **School start time** there saves the recurring preference. Progress and evaluations are clearly labelled samples; camera/microphone consent choices are real saved state, with no media input active. The evaluation flag belongs to this development launch command; parents cannot enable it. Omitting the flag requires reviewed content. The app and local services must be running for preparation and alarms; jobs and preferences survive shutdown, and the worker catches up on restart.

2026-10-14 policy update: 122 backend tests pass against the isolated QA database, including start-time persistence, forbidden parent overrides, daily rollover, missed-day recovery, role restrictions and preserving prepared work. These tests do not substitute for human content review or listening to narration.

The direct-only prepared review lecture is now `/lesson-demo`, using the same lesson window without a main-screen button. Its existing ready job is isolated from student session/progress writes. Current scheduling details: [DAILY_TIMETABLE.md](DAILY_TIMETABLE.md).


Runtime packaging update: use `docs/RUN_CURRENT_SYSTEM.md`. The code and inputs
now ship together. `docs/content/lesson-pairs.json` is the current 93-pair runtime
catalog (91 published plus two supplementary review drafts), replacing the older
77-pair/Downloads-path setup described in historical verification notes.
