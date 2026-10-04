"""Feature modules. One package per module; each owned by exactly one track (see CODEOWNERS).

Rules (enforced by import-linter in CI):
- A module never imports another module. Share data through /contracts and the session log.
- A module may import app.core and app.session_log.
- Optional `router.py` exposing `router` is mounted at /api/<module_name>.
"""
