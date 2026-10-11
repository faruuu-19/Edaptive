import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select

from app.core.db import DbSession
from app.core.household import StudentProfile, get_active_profile, get_household
from app.core.identity import CurrentActor, ParentActor, ensure_student_access

router = APIRouter()

DisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=30),
    Field(description="First name or nickname only"),
]
Grade = Annotated[int, Field(ge=1, le=5)]
AvatarKey = Annotated[str, Field(pattern=r"^[a-z0-9_-]{1,40}$")]


class ProfileOut(BaseModel):
    id: uuid.UUID
    display_name: str
    grade: int
    avatar_key: str


class ProfileCreate(BaseModel):
    display_name: DisplayName
    grade: Grade
    avatar_key: AvatarKey = "default"


class ProfileUpdate(BaseModel):
    display_name: DisplayName | None = None
    grade: Grade | None = None
    avatar_key: AvatarKey | None = None


def _out(profile: StudentProfile) -> ProfileOut:
    return ProfileOut(
        id=profile.id,
        display_name=profile.display_name,
        grade=profile.grade,
        avatar_key=profile.avatar_key,
    )


def _active_or_404(db, household_id: uuid.UUID, student_id: uuid.UUID) -> StudentProfile:
    profile = get_active_profile(db, household_id, student_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "profile not found")
    return profile


@router.get("")
def list_profiles(db: DbSession) -> list[ProfileOut]:
    """Public: the profile picker shows these before anyone is signed in. Name, grade and
    icon only; nothing else about a child is exposed here."""
    household = get_household(db)
    if household is None:
        return []
    profiles = db.scalars(
        select(StudentProfile)
        .where(StudentProfile.household_id == household.id, StudentProfile.archived_at.is_(None))
        .order_by(StudentProfile.created_at)
    )
    return [_out(p) for p in profiles]


@router.get("/{student_id}")
def get_profile(student_id: uuid.UUID, actor: CurrentActor, db: DbSession) -> ProfileOut:
    ensure_student_access(actor, student_id)
    return _out(_active_or_404(db, actor.household_id, student_id))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_profile(body: ProfileCreate, actor: ParentActor, db: DbSession) -> ProfileOut:
    profile = StudentProfile(household_id=actor.household_id, **body.model_dump())
    db.add(profile)
    db.flush()
    db.refresh(profile)
    return _out(profile)


@router.patch("/{student_id}")
def update_profile(
    student_id: uuid.UUID, body: ProfileUpdate, actor: ParentActor, db: DbSession
) -> ProfileOut:
    profile = _active_or_404(db, actor.household_id, student_id)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(profile, field, value)
    db.flush()
    return _out(profile)


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_profile(student_id: uuid.UUID, actor: ParentActor, db: DbSession) -> None:
    """Archive rather than delete: the session log keeps referring to this child's history."""
    _active_or_404(db, actor.household_id, student_id).archived_at = datetime.now(UTC)
