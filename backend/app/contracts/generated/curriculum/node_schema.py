# GENERATED from /contracts by tools/gen_contracts.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, RootModel
from ..common import ids_schema


class Level(StrEnum):
    unit = "unit"
    lesson = "lesson"


class Objective(RootModel[str]):
    root: Annotated[str, Field(min_length=1)]


class Source(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    name: str
    url: str | None = None
    license: str


class CurriculumNode(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: ids_schema.CurriculumNodeId
    subject: ids_schema.Subject
    grade: ids_schema.Grade
    level: Level
    title: Annotated[str, Field(min_length=1)]
    parent_id: ids_schema.CurriculumNodeId | None
    order: Annotated[int, Field(description="Position among siblings, starting at 1.", ge=1)]
    prerequisites: list[ids_schema.CurriculumNodeId]
    objectives: list[Objective] | None = None
    source: Source
