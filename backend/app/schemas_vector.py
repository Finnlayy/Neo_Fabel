"""Pydantic schemas for Phase 1 Qdrant vector APIs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class VectorPointIn(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    vector: list[float] = Field(min_length=1, max_length=4096)
    title: str | None = None
    category: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def strip_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("id must not be blank")
        return cleaned


class VectorUpsertRequest(BaseModel):
    points: list[VectorPointIn] = Field(min_length=1, max_length=200)


class VectorSearchRequest(BaseModel):
    vector: list[float] = Field(min_length=1, max_length=4096)
    top_k: int = Field(default=4, ge=1, le=50)
    score_threshold: float | None = Field(default=None, ge=-1.0, le=1.0)
    metric: Literal["cosine"] = "cosine"


class VectorEnsureRequest(BaseModel):
    """Optional body; collection/size come from settings when omitted."""

    collection: str | None = None
