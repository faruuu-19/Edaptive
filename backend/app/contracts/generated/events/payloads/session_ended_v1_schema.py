# GENERATED from /contracts by tools/gen_contracts.sh. Do not edit.

from __future__ import annotations

from enum import StrEnum
from pydantic import BaseModel, ConfigDict


class Reason(StrEnum):
    completed = "completed"
    exited = "exited"
    timeout = "timeout"


class SessionEndedV1(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    reason: Reason
