# GENERATED from /contracts by tools/gen_contracts.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field
from ..common import ids_schema


class Role(StrEnum):
    student = "student"
    parent = "parent"


class Actor(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    household_id: ids_schema.Uuid
    role: Annotated[
        Role,
        Field(
            description="student: a child using their own profile. parent: the guardian, unlocked for parent-only areas (dashboard, consent, schedule and privacy controls)."
        ),
    ]
    student_id: Annotated[
        ids_schema.Uuid | None,
        Field(
            description="The active student profile. Required for role student; null for parent unless the parent is viewing a specific child."
        ),
    ]
