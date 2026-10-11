import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.household import Household, StudentProfile, get_active_profile, get_household
from app.core.identity import Actor
from app.modules.auth.models import AuthSession, ParentPin
from app.modules.auth.pin import hash_pin, verify_pin

STUDENT_SESSION = timedelta(hours=12)
PARENT_SESSION = timedelta(minutes=15)  # parent areas re-lock quickly on a shared family device
MAX_PIN_ATTEMPTS = 5
PIN_LOCKOUT = timedelta(minutes=5)


class AuthError(Exception):
    def __init__(self, status: int, detail: str, retry_after: int | None = None):
        super().__init__(detail)
        self.status, self.detail, self.retry_after = status, detail, retry_after


def _now() -> datetime:
    return datetime.now(UTC)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _open_session(db: Session, household_id: uuid.UUID, role: str, student_id: uuid.UUID | None) -> str:
    token = secrets.token_urlsafe(32)
    ttl = PARENT_SESSION if role == "parent" else STUDENT_SESSION
    db.add(
        AuthSession(
            token_hash=_token_hash(token),
            household_id=household_id,
            role=role,
            student_id=student_id,
            expires_at=_now() + ttl,
        )
    )
    db.flush()
    return token


def setup_household(db: Session, pin: str) -> str:
    """First run only: create the household and the parent PIN, and sign the parent in."""
    if get_household(db) is not None:
        raise AuthError(409, "already set up")
    household = Household()
    db.add(household)
    db.flush()
    db.add(ParentPin(household_id=household.id, pin_hash=hash_pin(pin)))
    return _open_session(db, household.id, "parent", None)


def sign_in_parent(db: Session, pin: str) -> str:
    household = get_household(db)
    if household is None:
        raise AuthError(409, "not set up yet")
    record = db.get(ParentPin, household.id, with_for_update=True)
    now = _now()
    if record.locked_until and record.locked_until > now:
        raise AuthError(429, "too many attempts", int((record.locked_until - now).total_seconds()) + 1)
    if not verify_pin(pin, record.pin_hash):
        record.failed_attempts += 1
        if record.failed_attempts >= MAX_PIN_ATTEMPTS:
            record.failed_attempts, record.locked_until = 0, now + PIN_LOCKOUT
        # Commit now: the error below rolls the request back, which would erase the count.
        db.commit()
        raise AuthError(401, "wrong PIN")
    record.failed_attempts, record.locked_until = 0, None
    return _open_session(db, household.id, "parent", None)


def sign_in_student(db: Session, student_id: uuid.UUID) -> str:
    """Children pick their profile; no child passwords."""
    household = get_household(db)
    if household is None or get_active_profile(db, household.id, student_id) is None:
        raise AuthError(404, "profile not found")
    return _open_session(db, household.id, "student", student_id)


def sign_out(db: Session, token: str) -> None:
    db.execute(
        update(AuthSession)
        .where(AuthSession.token_hash == _token_hash(token), AuthSession.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def resolve_token(db: Session, token: str | None) -> Actor | None:
    if not token:
        return None
    session = db.scalars(
        select(AuthSession).where(
            AuthSession.token_hash == _token_hash(token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > _now(),
        )
    ).first()
    if session is None:
        return None
    if session.role == "student":
        # An archived profile signs out everywhere immediately.
        profile = db.get(StudentProfile, session.student_id)
        if profile is None or profile.archived_at is not None:
            return None
    return Actor(household_id=session.household_id, role=session.role, student_id=session.student_id)
