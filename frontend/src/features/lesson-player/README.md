# Lesson player — Amna / Track B

Public API: `LessonPlayer` from this folder's `index.ts`.

Shared player for scheduled Maths classes and opt-in lesson previews, using the public voice and avatar features. It follows `delivery_policy.main_path`, pauses at reflections and questions, and shows visual directions as captions. Scheduled classes retain position saving, finish/exit/rejoin controls, and child-friendly errors. Previews never write learner progress. No answer grading or mastery assessment is added.

The teacher model follows the selected voice and falls back to the 2D teacher if 3D loading or streaming is unavailable. The avatar's actual audio clock drives captions and completion; the last part cannot finish a scheduled class before the audio drains. See `docs/voice/TEACHER_AVATAR_INTEGRATION.md` and `voice_service/README.md` at the repository root.
