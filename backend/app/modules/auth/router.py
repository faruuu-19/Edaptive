import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import DbSession
from app.core.household import get_household
from app.core.identity import Actor, install_actor_resolver
from app.modules.auth import service
from app.modules.auth.pin import PIN_PATTERN
from app.session_log import append

COOKIE = "edaptive_session"

router = APIRouter()


def _resolve(request: Request, db: Session) -> Actor | None:
    return service.resolve_token(db, request.cookies.get(COOKIE))


def on_mount(api: FastAPI) -> None:
    install_actor_resolver(api, _resolve)


Pin = Annotated[str, Field(pattern=PIN_PATTERN.pattern, description="4-6 digits")]


class PinBody(BaseModel):
    pin: Pin


class StudentBody(BaseModel):
    student_id: uuid.UUID


class ActorOut(BaseModel):
    household_id: uuid.UUID
    role: str
    student_id: uuid.UUID | None


class StatusOut(BaseModel):
    setup_complete: bool
    actor: ActorOut | None


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(COOKIE, token, httponly=True, samesite="strict", path="/")


def _run(action):
    try:
        return action()
    except service.AuthError as exc:
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        raise HTTPException(exc.status, exc.detail, headers=headers) from None


@router.get("/status")
def auth_status(request: Request, db: DbSession) -> StatusOut:
    """Public: lets the UI decide between first-run setup, the profile picker and the app."""
    actor = _resolve(request, db)
    return StatusOut(
        setup_complete=get_household(db) is not None,
        actor=ActorOut(**actor.__dict__) if actor else None,
    )


@router.post("/setup", status_code=status.HTTP_201_CREATED)
def setup(body: PinBody, response: Response, db: DbSession) -> None:
    _set_cookie(response, _run(lambda: service.setup_household(db, body.pin)))


@router.post("/parent", status_code=status.HTTP_204_NO_CONTENT)
def unlock_parent(body: PinBody, response: Response, db: DbSession) -> None:
    _set_cookie(response, _run(lambda: service.sign_in_parent(db, body.pin)))


@router.post("/student", status_code=status.HTTP_204_NO_CONTENT)
def pick_profile(body: StudentBody, response: Response, db: DbSession) -> None:
    _set_cookie(response, _run(lambda: service.sign_in_student(db, body.student_id)))
    append(
        db,
        {
            "event_id": str(uuid.uuid4()),
            "event_type": "profile.selected",
            "event_version": 1,
            "occurred_at": datetime.now(UTC).isoformat(),
            "source": "auth",
            "session_id": None,
            "student_id": str(body.student_id),
            "payload": {},
        },
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DbSession) -> None:
    if token := request.cookies.get(COOKIE):
        service.sign_out(db, token)
    response.delete_cookie(COOKIE, path="/")
