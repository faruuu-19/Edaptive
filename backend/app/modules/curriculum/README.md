# curriculum

**Owner:** Track C · **Ships in:** Mid-1

Curriculum Compiler: turns source material into curriculum nodes and lesson JSON, loads them into the DB, serves them

Boundary: talks to other modules only through `/contracts` and the session log
(`app.session_log`). Add `router.py` with a `router = APIRouter()` to expose
endpoints at `/api/curriculum`.
