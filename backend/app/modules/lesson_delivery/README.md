# Lesson delivery

Amna's real lesson delivery and voice integration, with local scheduling/storage additions requested by Amna. Storage/scheduling boundaries and migration require Ibrahim's review before merge. APIs use the existing identity dependencies and Postgres session log; no feature imports another module's internals.

Schedules, durable local preparation jobs, source-linked generated scripts, lesson position and lifecycle survive restarts. Parent-only creation and retry, per-child access, grade-matched curriculum, and explicit parent draft-content opt-in. Science and English are coming soon. Script timing is an estimate from spoken words, assessment/reflection pauses and a three-minute buffer, clamped to 15–35 minutes; actual overruns preserve breaks.
