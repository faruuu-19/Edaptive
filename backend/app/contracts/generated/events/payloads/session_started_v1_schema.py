# GENERATED from /contracts by tools/gen_contracts.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field
from ...common import ids_schema


class Entry(StrEnum):
    scheduled = "scheduled"
    free_practice = "free_practice"


class SessionStartedV1(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    entry: Annotated[
        Entry, Field(description="How the session began: from the timetable or as free practice.")
    ]
    node_id: Annotated[
        ids_schema.CurriculumNodeId | None,
        Field(description="Curriculum node the session opens on, if known."),
    ] = None
