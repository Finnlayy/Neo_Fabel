"""Qdrant vector store client for Phase 1 neural vector APIs."""

from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse

from ..settings import Settings, get_settings

# Stable namespace so string document IDs map to deterministic Qdrant point UUIDs.
_POINT_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


class QdrantStoreError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def point_uuid(document_id: str) -> str:
    return str(uuid.uuid5(_POINT_NS, document_id))


def _normalize_vector(vector: list[float], size: int) -> list[float]:
    if len(vector) == size:
        return vector
    if len(vector) > size:
        return vector[:size]
    return vector + [0.0] * (size - len(vector))


class QdrantStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: AsyncQdrantClient | None = None

    @property
    def enabled(self) -> bool:
        return self.settings.qdrant_enabled

    @property
    def collection(self) -> str:
        return self.settings.qdrant_collection

    @property
    def vector_size(self) -> int:
        return self.settings.qdrant_vector_size

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise QdrantStoreError("qdrant_disabled", "Qdrant is disabled (QDRANT_ENABLED=false)")

    def client(self) -> AsyncQdrantClient:
        self._require_enabled()
        if self._client is None:
            kwargs: dict[str, Any] = {
                "url": self.settings.qdrant_url,
                "timeout": self.settings.qdrant_timeout_seconds,
            }
            if self.settings.qdrant_api_key:
                kwargs["api_key"] = self.settings.qdrant_api_key
            self._client = AsyncQdrantClient(**kwargs)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def health(self) -> dict[str, Any]:
        if not self.enabled:
            return {
                "status": "disabled",
                "enabled": False,
                "ready": False,
                "url": self.settings.qdrant_url,
                "collection": self.collection,
                "vector_size": self.vector_size,
            }
        try:
            client = self.client()
            # Prefer get_collections as a lightweight readiness probe.
            collections = await client.get_collections()
            names = [c.name for c in collections.collections]
            return {
                "status": "ok",
                "enabled": True,
                "ready": True,
                "url": self.settings.qdrant_url,
                "collection": self.collection,
                "collection_exists": self.collection in names,
                "vector_size": self.vector_size,
                "collections": names,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "unavailable",
                "enabled": True,
                "ready": False,
                "url": self.settings.qdrant_url,
                "collection": self.collection,
                "vector_size": self.vector_size,
                "error": str(exc),
            }

    async def ensure_collection(self) -> dict[str, Any]:
        self._require_enabled()
        client = self.client()
        exists = await client.collection_exists(self.collection)
        created = False
        if not exists:
            await client.create_collection(
                collection_name=self.collection,
                vectors_config=qmodels.VectorParams(
                    size=self.vector_size,
                    distance=qmodels.Distance.COSINE,
                ),
            )
            created = True
        info = await client.get_collection(self.collection)
        return {
            "collection": self.collection,
            "created": created,
            "exists": True,
            "points_count": info.points_count,
            "vector_size": self.vector_size,
            "distance": "Cosine",
        }

    async def upsert_points(self, points: list[dict[str, Any]]) -> dict[str, Any]:
        self._require_enabled()
        if not points:
            raise QdrantStoreError("empty_points", "points must be a non-empty list")
        await self.ensure_collection()
        client = self.client()
        q_points: list[qmodels.PointStruct] = []
        for raw in points:
            doc_id = str(raw.get("id") or "").strip()
            if not doc_id:
                raise QdrantStoreError("invalid_point", "each point requires a non-empty id")
            vector = raw.get("vector")
            if not isinstance(vector, list) or not vector:
                raise QdrantStoreError("invalid_point", f"point {doc_id} requires a vector list")
            try:
                floats = [float(v) for v in vector]
            except (TypeError, ValueError) as exc:
                raise QdrantStoreError("invalid_point", f"point {doc_id} vector must be numeric") from exc
            payload = dict(raw.get("payload") or {})
            payload["id"] = doc_id
            if "title" in raw and "title" not in payload:
                payload["title"] = raw["title"]
            if "category" in raw and "category" not in payload:
                payload["category"] = raw["category"]
            if "metadata" in raw and "metadata" not in payload:
                payload["metadata"] = raw["metadata"]
            q_points.append(
                qmodels.PointStruct(
                    id=point_uuid(doc_id),
                    vector=_normalize_vector(floats, self.vector_size),
                    payload=payload,
                )
            )
        try:
            await client.upsert(collection_name=self.collection, points=q_points, wait=True)
        except UnexpectedResponse as exc:
            raise QdrantStoreError("qdrant_upsert_failed", str(exc), retryable=True) from exc
        return {
            "upserted": len(q_points),
            "collection": self.collection,
            "ids": [str(p.payload.get("id")) for p in q_points if p.payload],
        }

    async def search(
        self,
        vector: list[float],
        *,
        top_k: int = 4,
        score_threshold: float | None = None,
    ) -> dict[str, Any]:
        self._require_enabled()
        if not vector:
            raise QdrantStoreError("invalid_query", "vector must be a non-empty list")
        try:
            floats = [float(v) for v in vector]
        except (TypeError, ValueError) as exc:
            raise QdrantStoreError("invalid_query", "vector must be numeric") from exc
        await self.ensure_collection()
        client = self.client()
        limit = max(1, min(int(top_k), 50))
        try:
            response = await client.query_points(
                collection_name=self.collection,
                query=_normalize_vector(floats, self.vector_size),
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False,
            )
        except UnexpectedResponse as exc:
            raise QdrantStoreError("qdrant_search_failed", str(exc), retryable=True) from exc
        results = []
        for hit in response.points:
            payload = dict(hit.payload or {})
            results.append(
                {
                    "id": str(payload.get("id") or hit.id),
                    "score": float(hit.score if hit.score is not None else 0.0),
                    "title": payload.get("title"),
                    "category": payload.get("category"),
                    "metadata": payload.get("metadata") or {},
                    "payload": payload,
                }
            )
        return {
            "collection": self.collection,
            "metric": "cosine",
            "top_k": limit,
            "count": len(results),
            "results": results,
        }

    async def list_points(self, *, limit: int = 100) -> dict[str, Any]:
        self._require_enabled()
        await self.ensure_collection()
        client = self.client()
        records, _next = await client.scroll(
            collection_name=self.collection,
            limit=max(1, min(int(limit), 500)),
            with_payload=True,
            with_vectors=True,
        )
        points = []
        for record in records:
            payload = dict(record.payload or {})
            vector = record.vector
            if isinstance(vector, dict):
                # Named vectors — take first list value.
                vector = next((v for v in vector.values() if isinstance(v, list)), [])
            points.append(
                {
                    "id": str(payload.get("id") or record.id),
                    "title": payload.get("title"),
                    "category": payload.get("category"),
                    "vector": vector if isinstance(vector, list) else [],
                    "metadata": payload.get("metadata") or {},
                    "payload": payload,
                }
            )
        return {"collection": self.collection, "count": len(points), "points": points}

    async def delete_point(self, document_id: str) -> dict[str, Any]:
        self._require_enabled()
        doc_id = document_id.strip()
        if not doc_id:
            raise QdrantStoreError("invalid_id", "id is required")
        await self.ensure_collection()
        client = self.client()
        await client.delete(
            collection_name=self.collection,
            points_selector=qmodels.PointIdsList(points=[point_uuid(doc_id)]),
            wait=True,
        )
        return {"deleted": True, "id": doc_id, "collection": self.collection}


_store: QdrantStore | None = None


def get_qdrant_store() -> QdrantStore:
    global _store
    if _store is None:
        _store = QdrantStore()
    return _store


def reset_qdrant_store_for_tests() -> None:
    global _store
    _store = None
