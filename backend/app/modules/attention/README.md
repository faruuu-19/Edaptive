# attention

**Owner:** Track C · **Ships in:** Mid-2

Server side of the Attention Pipeline: receives on-device engagement scores only (never video)

Boundary: talks to other modules only through `/contracts` and the session log
(`app.session_log`). Add `router.py` with a `router = APIRouter()` to expose
endpoints at `/api/attention`.
