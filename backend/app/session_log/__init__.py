"""The shared, append-only session log (owned by Track C).

Any module may import `append` and `read`; nothing may update or delete events.
"""

from app.session_log.store import append, read

__all__ = ["append", "read"]
