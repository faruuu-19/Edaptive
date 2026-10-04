# parent

**Owner:** Track C · **Ships in:** Mid-2

Parent Dashboard backend (v1 in Mid-2), schedule and privacy controls in Final-2

Boundary: talks to other modules only through `/contracts` and the session log
(`app.session_log`). Add `router.py` with a `router = APIRouter()` to expose
endpoints at `/api/parent`.
