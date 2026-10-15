"""Who is acting on a request: the single seam between the auth module and every other module.

Identity hierarchy: household -> parent -> students. The auth module (Track C) decides *how*
someone is identified and installs a resolver at startup; every other module only declares
what it needs:

    def handler(actor: CurrentActor): ...        # any signed-in student or parent
    def handler(actor: ParentActor): ...         # parent-only (dashboard, consent, controls)
    ensure_student_access(actor, student_id)     # a student may only touch their own data

No resolver installed means nobody is signed in: requests fail closed with 401.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.db import DbSession


@dataclass(frozen=True)
class Actor:
    """Mirrors contracts/auth/actor.schema.json."""

    household_id: uuid.UUID
    role: Literal["student", "parent"]
    student_id: uuid.UUID | None

    def __post_init__(self) -> None:
        if self.role == "student" and self.student_id is None:
            raise ValueError("a student actor must have a student_id")

    def can_access_student(self, student_id: uuid.UUID) -> bool:
        return self.role == "parent" or self.student_id == student_id


# Gets the request's DB session so lookups share the request's transaction.
ActorResolver = Callable[[Request, Session], Actor | None]


def install_actor_resolver(api: FastAPI, resolver: ActorResolver) -> None:
    """Called once by the auth module when it is mounted."""
    api.state.actor_resolver = resolver


def get_actor(request: Request, db: DbSession) -> Actor:
    resolver: ActorResolver | None = getattr(request.app.state, "actor_resolver", None)
    actor = resolver(request, db) if resolver else None
    if actor is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not signed in")
    return actor


CurrentActor = Annotated[Actor, Depends(get_actor)]


def require_parent(actor: CurrentActor) -> Actor:
    if actor.role != "parent":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "parent access required")
    return actor


ParentActor = Annotated[Actor, Depends(require_parent)]


def ensure_student_access(actor: Actor, student_id: uuid.UUID) -> None:
    if not actor.can_access_student(student_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your profile")
