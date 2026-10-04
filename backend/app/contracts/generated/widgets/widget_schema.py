# GENERATED from /contracts by tools/gen_contracts.sh. Do not edit.

from __future__ import annotations

from typing import Annotated, Any
from pydantic import BaseModel, ConfigDict, Field


class WidgetRef(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    widget_type: Annotated[str, Field(pattern="^[a-z][a-z_]*$")]
    props: dict[str, Any]
