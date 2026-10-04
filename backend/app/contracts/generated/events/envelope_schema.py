# GENERATED from /contracts by tools/gen_contracts.sh. Do not edit.

from __future__ import annotations

from typing import Annotated, Any
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from ..common import ids_schema


class EventEnvelope(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    event_id: ids_schema.Uuid
    event_type: Annotated[
        str,
        Field(
            description="<namespace>.<name>. The namespace decides which track owns the type (see registry.json).",
            pattern="^[a-z]+\\.[a-z][a-z_]*$",
        ),
    ]
    event_version: Annotated[
        int, Field(description="Version of the payload schema for this event_type.", ge=1)
    ]
    occurred_at: AwareDatetime
    source: Annotated[
        str,
        Field(
            description="Module that emitted the event, e.g. curriculum, socratic_engine, lesson_player.",
            pattern="^[a-z][a-z_]*$",
        ),
    ]
    session_id: Annotated[
        ids_schema.Uuid | None,
        Field(
            description="Learning session this belongs to; null for events outside a session (e.g. profile.selected)."
        ),
    ]
    student_id: Annotated[
        ids_schema.Uuid | None,
        Field(description="Student profile; null only for household-level events (e.g. parent actions)."),
    ]
    payload: Annotated[
        dict[str, Any],
        Field(
            description="Shape depends on event_type; validated against the payload schema listed in registry.json."
        ),
    ]
