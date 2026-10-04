# scheduling

**Owner:** Track C · **Ships in:** Final-1

Scheduling Engine (daily timetable) and, in Final-2, the Schedule-Enforcement Service

Boundary: talks to other modules only through `/contracts` and the session log
(`app.session_log`). Add `router.py` with a `router = APIRouter()` to expose
endpoints at `/api/scheduling`.
