# GENERATED from /contracts by tools/gen_contracts.sh. Do not edit.

from __future__ import annotations

from typing import Annotated, Any, Literal
from pydantic import BaseModel, ConfigDict, Field, RootModel
from enum import StrEnum
from ..widgets import widget_schema
from ..common import ids_schema


class Objective(RootModel[str]):
    root: Annotated[str, Field(min_length=1)]


class Kind(StrEnum):
    explain = "explain"
    practice = "practice"
    check = "check"


class Verifier(StrEnum):
    sympy = "sympy"
    grammar = "grammar"
    concept_card = "concept_card"


class Check(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    verifier: Verifier
    spec: dict[str, Any]


class Step(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    step_id: Annotated[str, Field(pattern="^[a-z0-9][a-z0-9-]*$")]
    kind: Kind
    prompt: str | None = None
    widget: widget_schema.WidgetRef | None = None
    check: Check | None = None


class Lesson(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    schema_version: Literal[1]
    node_id: ids_schema.CurriculumNodeId
    title: Annotated[str, Field(min_length=1)]
    subject: ids_schema.Subject
    grade: ids_schema.Grade
    objectives: list[Objective] | None = None
    steps: Annotated[list[Step], Field(min_length=1)]
