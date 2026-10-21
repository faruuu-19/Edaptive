# Lesson delivery

Amna's lesson delivery and local voice integration. The recurring scheduling and storage boundary is a local integration for Ibrahim to review before merge. Existing identity dependencies protect all APIs; no module imports another module's internals.

Parents supply only a per-child **daily school start time** (`HH:MM`, Asia/Karachi). `PUT /api/lesson_delivery/routine/{student_id}` rejects lesson IDs, dates, break durations, preparation durations and draft flags. The operational preference lives in `lesson_school_routine`; generated schedules and lesson positions live in `lesson_timetable`. Migration 0004 adds the preference without changing profiles or existing sessions.

The system chooses the next available paired Maths lesson in module/lesson order within the child's grade. Missing lesson or module numbers do not block later pairs; another grade is never substituted. It assigns the calendar day, estimates preparation lead time, and estimates class duration from the prepared script (15–35 minutes including three minutes of buffer). Break policy is internal. At this stage there is one working Maths class per daily plan plus Science, English and Physical class as inactive 20-minute Coming soon slots. Provisional duration is 20 minutes including buffer; script timing replaces it and shifts the rest of the day. Module/lesson delivery state is persisted in `lesson_learning_progress`; gaps remain visible there, and unknown module coverage cannot be marked complete. Lesson delivery completion is not mastery or an assessment result. Placement, adaptive sequencing, progress graphs, evaluations and consent remain their respective modules.

The worker automatically plans the following school day after delivery, resumes after restarts and moves an unattended old-day class to the next school time while keeping its prepared job. Changing a time moves an upcoming class; it never interrupts a class already in progress. A parent cannot start, borrow, finish or narrate a student's class through the API. The student retains Start, Borrow five minutes, pause, replay and Exit.

Draft content is disabled by default. Only an operator can enable audited drafts for local evaluation using `EDAPTIVE_ALLOW_DRAFT_LESSONS=1` (launcher flag `--allow-draft-lessons`). This is not content approval and is not a parental scheduling choice. Without eligible content, the preference is saved and the system reports that review/content is awaited. A stopped local service is retried automatically.

## Leave and rejoin

An exited class stays active until its original end time (20 minutes after the first start).
Routine refreshes preserve its job, saved segment, narration history and timetable times,
including when the parent changes the daily start time. Rejoining has no exit-count limit
and does not extend the deadline or regenerate the lesson. If the child is still out at
the deadline, attendance is absent regardless of the percentage heard, the attempt is
closed as unfinished, and the next school day advances to the next lesson. Completed
lessons retain their existing attendance checks.
