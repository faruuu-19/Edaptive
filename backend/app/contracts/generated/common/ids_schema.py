# GENERATED from /contracts by tools/gen_contracts.sh. Do not edit.

from __future__ import annotations

from typing import Annotated, Any
from pydantic import Field, RootModel
from uuid import UUID
from enum import StrEnum


class CommonIdentifiers(RootModel[Any]):
    root: Annotated[Any, Field(title="Common identifiers")]


class Uuid(RootModel[UUID]):
    root: Annotated[UUID, Field(pattern="^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")]


class CurriculumNodeId(RootModel[str]):
    root: Annotated[
        str,
        Field(
            description="Stable dotted id: <subject>.g<grade>[.<segment>]*, e.g. math.g3.m5.l12. Never reuse or renumber once published.",
            pattern="^(math|english|science)\\.g[1-5](\\.[a-z0-9][a-z0-9-]*)*$",
        ),
    ]


class Subject(StrEnum):
    math = "math"
    english = "english"
    science = "science"


class Grade(RootModel[int]):
    root: Annotated[int, Field(ge=1, le=5)]


class Track(StrEnum):
    track_a = "track-a"
    track_b = "track-b"
    track_c = "track-c"
