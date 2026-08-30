"""Typed, non-verdict-changing source explanation hints."""

from typing import Literal

from pydantic import BaseModel, Field


class SourceHint(BaseModel):
    """A source construct that may explain a behavioural failure."""

    component: Literal["feature", "forecast"]
    callable_ref: str = Field(min_length=1)
    rule: str = Field(min_length=1)
    message: str = Field(min_length=1)
    line: int = Field(gt=0)
    path: str | None = None
