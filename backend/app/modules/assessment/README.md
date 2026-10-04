# assessment

**Owner:** Track C · **Ships in:** Final-1

Assessment Backend: scheduled quizzes, immediate feedback, progress projections

Boundary: talks to other modules only through `/contracts` and the session log
(`app.session_log`). Add `router.py` with a `router = APIRouter()` to expose
endpoints at `/api/assessment`.
