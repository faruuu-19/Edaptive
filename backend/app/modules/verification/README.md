# verification

**Owner:** Track A · **Ships in:** Mid-1

Deterministic verifiers (SymPy, then grammar and concept-card RAG) that gate every tutor claim

Boundary: talks to other modules only through `/contracts` and the session log
(`app.session_log`). Add `router.py` with a `router = APIRouter()` to expose
endpoints at `/api/verification`.
