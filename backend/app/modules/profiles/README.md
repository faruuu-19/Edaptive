# profiles

**Owner:** Track C · **Ships in:** Mid-1

Household and student profiles behind the Home & Profile UI

Boundary: talks to other modules only through `/contracts` and the session log
(`app.session_log`). Add `router.py` with a `router = APIRouter()` to expose
endpoints at `/api/profiles`.
