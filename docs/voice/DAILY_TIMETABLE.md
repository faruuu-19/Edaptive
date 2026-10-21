# Automatic daily timetable and prepared demo — 14 October 2026

The student home (`/home`) retains Ibrahim's subject cards and adds the real per-child day plan below them. The parent supplies only daily school start time in `/parent/<student_id>`. Schedule data is in Postgres, not a fabricated client clock.

The current daily order is Maths → Science → English → Physical class, with system-owned five-minute breaks. Each unprepared class reserves **20 minutes total**, including three minutes of buffer. Only Maths is implemented. Science, English and Physical class say Coming soon, never create preparation jobs, never ring alarms, and never claim completion. Maths says Coming soon while its actual preparation progresses.

For ready Maths scripts, the existing local service estimates narration plus reflection/question response pauses, then includes a three-minute buffer and a 15–35-minute total window. The server replaces the provisional window and shifts every later class and break by the duration difference. The buffer is inside the class window; breaks are separate. Borrow/Snooze shifts all remaining slots five minutes. Actual late starts and overruns also move later slots.

The routine worker prepares ahead of the scheduled class using its estimated preparation lead time, real local script generation, validation and voice warm-up. UI percentage comes from actual preparation state. A class cannot start before its scheduled time or before readiness. The open student app rings using local Web Audio when the lesson is ready and its actual start time arrives, with Join and Snooze controls. The parent must allow the lesson alarm for that child; tapping the child's profile unlocks browser audio, and a visible Enable sound action appears if the browser still blocks it. An open app/tab and running local services are needed. Returning from class to Home stops playback but leaves the active class and saved position resumable. An unattended class releases voice resources after 90 seconds without a heartbeat.

`lesson_learning_progress` (migration 0006) stores the per-child Maths curriculum projection: lessons pending/in progress/delivered, module delivery counts, known module coverage and next required lesson. Timetables and session events remain the durable delivery history. An actual Start marks in-progress; Finish requires final narration and marks delivered. Delivery is not assessed mastery. The parent dashboard's sample evaluation/progress cards are unchanged and visibly labelled samples.

Required lessons come from the repository's concept collections, explicit `lessons_expected` metadata, and matched card IDs. The schedule chooses the next available pair in the same grade, ordered by module and lesson number, even when earlier numbers have no pair. Gaps remain visible in progress. A partial contiguous export alone does not prove complete module coverage; a module with unknown required size is never labelled complete. The legacy G2 M1 source explicitly covers Lessons 1–8. G2 M3 explicitly expects 21 lessons. When a new pair becomes available in the installed catalog and no lesson is planned, the worker can activate the existing unavailable Maths slot without replacing the day's identity. Curriculum sources and the voice paired inventory must be updated/validated by their owners; this implementation does not invent missing cards.

## Separate prepared demo

`/lesson-demo` has no link or button on Home, the parent dashboard or the profile screen. It uses the same LessonPlayer and existing ready **Pairs to ten** job, with live local Kokoro speech. It makes no script-generation submission, learning-session event or curriculum-progress update. It is independent of selected child history. Demo speech reserves the same local voice resource and releases it when finished or closed; an active different delivery reservation is respected.

The local launcher automatically finds an existing ready Pairs-to-ten job, or accepts `--demo-job-id <ready-job-uuid>`. It sets `EDAPTIVE_VOICE_PREVIEW=1` and `EDAPTIVE_DEMO_JOB_ID` for the local review route. Without a ready configured job, the demo route is disabled; it never generates a replacement on its own. Scheduled lessons continue using their own preparation jobs.

The current backend suite covers all four slots, no inactive alarms/jobs, changing 20→31 minutes with breaks preserved, persistent progression across missing lesson and module numbers within the same grade, and activating a newly available pair in place. Earlier demo checks loaded 19 main-path sections and produced three valid 24 kHz Kokoro audio frames (9.9 seconds) through the local HTTP proxy. No additional script was generated for that demo check. These checks do not replace human review of draft teaching content.


Runtime packaging update: use `docs/RUN_CURRENT_SYSTEM.md`. The code and inputs
now ship together. `docs/content/lesson-pairs.json` is the current 93-pair runtime
catalog (91 published plus two supplementary review drafts), replacing the older
77-pair/Downloads-path setup described in historical verification notes.
