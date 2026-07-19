"""Pydantic schemas for Phase 1 Qdrant vector APIs."""

from __future__ import annotations

import json
import math
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


MAX_POINT_AUXILIARY_BYTES = 16 * 1024


class VectorPointIn(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    vector: list[float] = Field(min_length=1, max_length=4096)
    title: str | None = Field(default=None, max_length=512)
    category: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def strip_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("id must not be blank")
        return cleaned

    @field_validator("vector")
    @classmethod
    def finite_vector(cls, value: list[float]) -> list[float]:
        if any(not math.isfinite(component) for component in value):
            raise ValueError("vector values must be finite")
        return value

    @model_validator(mode="after")
    def bounded_auxiliary_payload(self) -> "VectorPointIn":
        encoded = json.dumps(
            {"metadata": self.metadata, "payload": self.payload},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > MAX_POINT_AUXILIARY_BYTES:
            raise ValueError(f"metadata and payload must not exceed {MAX_POINT_AUXILIARY_BYTES} bytes")
        return self


class VectorUpsertRequest(BaseModel):
    points: list[VectorPointIn] = Field(min_length=1, max_length=50)


class VectorSearchRequest(BaseModel):
    vector: list[float] = Field(min_length=1, max_length=4096)
    top_k: int = Field(default=4, ge=1, le=50)
    score_threshold: float | None = Field(default=None, ge=-1.0, le=1.0)
    metric: Literal["cosine"] = "cosine"


class VectorEnsureRequest(BaseModel):
    """Optional body; collection/size come from settings when omitted."""

    collection: str | None = None
