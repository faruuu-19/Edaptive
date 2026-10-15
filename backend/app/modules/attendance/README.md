# attendance

Owner: Amna (Track B) with Ibrahim (Track C) reviewing, because parents read it.

Read-only attendance log for the parent dashboard: `GET /api/attendance/{student_id}` (parent only).

There is no table. `lesson_delivery` appends one `lesson.attendance_recorded` event per class attempt
when the attempt is final, and this module reads those events back. A child is **present** when they
stayed for at least 70% of the lesson (the parts they listened to), otherwise **absent**. See
`docs/voice/CLASS_EXIT_RULES.md` ("Attendance").

The recorded-lectures library (watching the part of a lesson that was missed) is a later iteration.
