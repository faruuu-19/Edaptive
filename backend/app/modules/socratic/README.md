# socratic

**Owner:** Track A · **Ships in:** Mid-1

Socratic Engine: the only place the local LLM is called (1-2 calls per turn, schema-constrained)

Boundary: talks to other modules only through `/contracts` and the session log
(`app.session_log`). Add `router.py` with a `router = APIRouter()` to expose
endpoints at `/api/socratic`.
