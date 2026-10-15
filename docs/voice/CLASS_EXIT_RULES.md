# Leaving a live class: the rules

Edaptive's class is a live, timed lesson with an AI teacher. A child may leave it (they are
a child, after all), but a lesson that starts and stops at the child's whim would disturb the
rest of the day. These are the rules the system follows. They are implemented in
`backend/app/modules/lesson_delivery/runtime.py` and covered by `backend/tests/test_lesson_delivery.py`.

## Principles

1. **The clock belongs to the day, not to one child's exit.** Leaving a class never moves the
   next class, a break, or tomorrow's start time. Only two things move the clock: a single
   snooze *before* class, and a class that overruns its time (it lengthens the following break).
2. **The child decides, but must confirm.** "Leave class" asks first, in plain words. The safe
   choice ("No, stay in class") is the default.
3. **A place is never lost.** The lesson part the child reached is saved.
4. **A lesson never reappears.** A lesson that was held but not finished (left early, or never joined) is closed for good: the next school day brings the *next* lesson. The unfinished lesson is meant for the recorded lessons library (a future iteration), not for repeating the class.
5. **A class that is not ready is moved, not skipped.** If class time comes and the lesson is still being prepared, the system works out the delay from the preparation so far, moves this class and everything after it, and tells the child and the parent the new time.
6. **The parent can always see what happened.** Today's class on the parent dashboard says who
   left, when, at which part, and what happens next.
7. **Controls belong to the right person.** Only the child can join, snooze, leave or rejoin.
   Whether the class alarm makes a sound is a *parent* permission; the child has no alarm control.

## What happens

| Situation | What the system does | Clock |
|---|---|---|
| Child taps **Leave class** and confirms | Class is marked *left*; the teacher voice is released (frees memory); place and reason are saved; `session.ended (exited)` is logged | Nothing moves |
| Child wants to **come back** | **Rejoin class** resumes at the saved part. Allowed until the class's scheduled end time | Nothing moves |
| Child leaves a **second time** | The class is over for today (*unfinished*): no more rejoining | Nothing moves |
| Class time **ends** while the child is out | *Unfinished*; rejoining is refused with a clear message | Nothing moves |
| **Connection lost** (no heartbeat for 2 minutes) | Treated as leaving, reason *connection lost*; `session.ended (timeout)` is logged. A closed tab can no longer leave a class "running" forever | Nothing moves |
| A lesson was **left early or never joined** | It is closed as *unfinished* (attendance logged as absent, or present if 70% was reached). It does **not** return; the next school day plans the next lesson. A lesson that was never ready is not counted absent and is tried again | Later days plan normally |
| Class time comes and the **lesson is not ready** | The class moves later by the estimated remaining preparation (whole 5-minute steps, at most 60 per step, 4 hours in total); later slots and breaks move with it; the child and parent see "will start at X instead of Y". Checked again at the new time. A failed preparation is not waited for | Moves this class and later ones |
| Child **finishes** | Delivered; curriculum advances | Overrun lengthens the following break (as before) |
| **Snooze** | Only before class, only once per class | Moves this class and all later ones by 5 minutes (as before) |
| **Parent** | Sees the status; cannot join, leave or snooze for the child | n/a |

Other classes (Science, English, Physical class are placeholders today) keep their times when
Maths is left early. The child simply waits for the next class.

## What the child sees

- During class: **Leave class** button at the top.
- Dialog: "Leaving class? Please confirm that you're going. Your teacher will save your place,
  and you can come back before class time ends." Buttons: **Yes, I'm going** / **No, stay in class**.
- After leaving: "You left Maths class. You can come back until 4:58 pm. Your place is saved." and **Rejoin class**.
- Once the class can no longer be rejoined: "Maths class has finished for today. Tomorrow you'll start your next Maths lesson."
- Class moved because the lesson was not ready: "Maths starts at 9:45 pm" with "Your Maths class will start at 9:45 pm instead of 9:30 pm. Your lesson is still being prepared."

## What the parent sees

*Today's class* on the child's dashboard: waiting / class time started / in class (part N of M) /
**left the class** (time, part, whether they chose to or the connection was lost, rejoin deadline) /
**class ended unfinished** (what happens next), **class moved** (new time and why) / finished. A left class is highlighted as
"Needs your attention". The page refreshes every few seconds; there is no push notification.

## Numbers you can change

`MAX_EXITS = 2` and `DISCONNECT_MS = 120_000` in `runtime.py`. The rejoin window is the class's
scheduled end (`end_ms`).

## Contract and data changes

- `lesson.delivery_changed` gains the actions `exit` and `rejoin` (additive; regenerated TS types).
- `session.ended` already allows `exited` and `timeout`; rejoining logs a new `session.started`.
- New consent kind `lesson_alarm` (migration `0007`), readable by the child's device through
  `GET /api/consent/{student_id}/lesson-alarm` and changeable only by the parent.

## Questions for the team

1. Should a parent get a push notification when a child leaves, not only the dashboard status?
2. When the recorded lessons library is built, should an unfinished lesson be offered there automatically?
3. If the day has a free slot later, should the system offer a make-up slot instead of waiting
   for tomorrow?
4. Should leaving early affect rewards or streaks (not built)?
5. Two exits per class and a two-minute connection timeout are first guesses; are they right?
