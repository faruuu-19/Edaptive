# Timetable, advance preparation and live class — Amna / Track B

How a scheduled class works end to end. All of it is local and offline: no cloud model, no paid API, no stored student audio.
Every card is still a **draft**; a parent must explicitly allow drafts, and the screen shows a "Draft" label.
The source of truth for matched content is the audited inventory in `docs/voice/PAIR_INVENTORY.md` (77 three-level draft pairs: 75 published, 2 local Grade 3). No pair is approved for child delivery.

## Where things live

| Piece | Location | Persistence |
|---|---|---|
| Timetable, slots, class phase, saved lesson position | `backend/app/modules/lesson_delivery/` (Postgres table `lesson_timetable`) | survives restarts |
| Preparation jobs (progress, checkpoints, ready script) | `voice_service/jobs.py` (SQLite at `~/edaptive-voice/jobs/`) | survives restarts |
| Script generation | `voice_service/preparation_worker.py` → existing script agent + local Qwen | checkpoint per job |
| Teacher voice | `voice_service/service.py` (Kokoro, loopback only) | in memory only |
| Screens | `/timetable` (`frontend/src/features/lesson-player/Timetable.tsx`) | — |

`/timetable-demo` only redirects to `/timetable`. There is no separate demo path.

## Flow

1. **Plan.** A parent creates a timetable for a child: a start time (with time zone, between three seconds and seven days ahead), the matched Maths lesson(s) for the child's grade, break length (default 5 min) and how early to prepare. Science and English are listed as "Coming soon"; no lesson is invented for them. A child has at most one active timetable.
2. **Prepare.** From `start − lead time` a backend worker submits a job to the voice service. The worker runs the script agent with the installed `qwen3.5:9b-q4_K_M`, one script section at a time. Progress is `completed sections / total` plus planning, validation and voice warm-up, never a timer. A memory guard pauses (not fails) the job when swap grows past 512 MiB or pressure turns critical, and the job resumes from its checkpoint.
3. **Validate.** Flagged sections get up to two repair rounds. A script that still has flags is not marked ready, and Start stays disabled.
4. **Duration.** Estimated from the prepared script (narration, thinking pauses, assessment response time plus a buffer), clamped to 15–35 minutes, with the basis shown. If a lesson overruns, later slots move and the break length is kept.
5. **Alarm.** At class time the open browser tab rings and offers **Start class** or **Borrow 5 minutes**. Start is refused by the server unless the time has come *and* preparation is ready.
6. **Borrow.** Moves this class and every later slot five minutes; breaks keep their length; finished preparation is kept.
7. **Class.** Start creates a real session (`session.started`), reserves the voice, and narrates the main path through live Kokoro. The child can pause, resume and replay. Reflection and question sections wait for Continue; at this stage questions are spoken with thinking pauses only. There is no answer submission, grading, hint or follow-up.
8. **Finish / cancel.** Finish is accepted only after the last part has been narrated. Both `finish` and `cancel` release the voice, which unloads Kokoro to free memory. An unattended class (no heartbeat for 90 s) releases it the same way; its saved position is kept in the timetable.

## Memory behaviour

Qwen and Kokoro are never both loaded for long. Kokoro releases its weights while Qwen prepares. A preparation for a later lesson **yields** to a class that is starting: it is paused, and it resumes from its checkpoint once the class releases the voice. (Until 2026-10-13 a yielded job stayed paused forever; this is now covered by `voice_service/test_jobs.py`.) Because the voice may be unloaded between classes, Start allows up to 60 s to reload it.

## Events

Registered by Ibrahim: `profile.selected`, `session.started`, `session.ended`. This module also emits `lesson.delivery_changed`, which is **not agreed with him**: it sits in its own commit on this branch ("CONTESTED") and in `docs/voice/EVENTS_PROPOSAL.md`. Do not push it before he approves.

## Verification status

- Backend tests (run against the isolated QA database, never the household's), voice-service tests, script-agent tests, frontend lint, typecheck and build pass.
- **Not yet shown end to end on this build:** a fresh Qwen preparation followed by a real alarm, Borrow, Start and finish in the browser. Memory was already tight (about 2.4 GB of 4 GB swap in use), so this is waiting for Amna's go-ahead.
- Heuristic checks on the script (numbers, equations, coverage, leakage) do not prove pedagogical quality. Human review is still required.
- The browser alarm needs an open tab and one click to enable sound. It is not an OS alarm or push notification.
