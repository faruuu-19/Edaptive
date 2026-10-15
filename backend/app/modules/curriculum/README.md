# curriculum

**Owner:** Track C · **Ships in:** Mid-1

Curriculum Compiler: validates the curriculum content (concept cards, assessments), loads it into the DB, serves it

Boundary: talks to other modules only through `/contracts` and the session log
(`app.session_log`). Add `router.py` with a `router = APIRouter()` to expose
endpoints at `/api/curriculum`.
