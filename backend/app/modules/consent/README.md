# consent

**Owner:** Track C · **Ships in:** Mid-2

Consent Model: camera/mic and data consent, checked before any gated feature runs

Boundary: talks to other modules only through `/contracts` and the session log
(`app.session_log`). Add `router.py` with a `router = APIRouter()` to expose
endpoints at `/api/consent`.
