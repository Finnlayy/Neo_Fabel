"""Focused tests for Phase 1 Qdrant vector routes (mocked client)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.auth import require_user
from backend.app.integrations import qdrant_store as store_module
from backend.app.main import app
from backend.app.routers import vector as vector_router
from backend.app.settings import get_settings

client = TestClient(app)


@pytest.fixture
def authenticated_user() -> None:
    app.dependency_overrides[require_user] = lambda: {
        "uid": "vector-test-user",
        "email_verified": True,
        "firebase": {"sign_in_provider": "google.com"},
    }
    yield
    app.dependency_overrides.pop(require_user, None)


class FakeStore:
    def __init__(self, *, enabled: bool = True, ready: bool = True) -> None:
        self.enabled = enabled
        self._ready = ready
        self.collection = "neo_fabel_vectors"
        self.vector_size = 8
        self.points: dict[str, dict[str, Any]] = {}

    async def health(self) -> dict[str, Any]:
        if not self.enabled:
            return {
                "status": "disabled",
                "enabled": False,
                "ready": False,
                "url": "http://localhost:6333",
                "collection": self.collection,
                "vector_size": self.vector_size,
            }
        if not self._ready:
            return {
                "status": "unavailable",
                "enabled": True,
                "ready": False,
                "url": "http://localhost:6333",
                "collection": self.collection,
                "vector_size": self.vector_size,
                "error": "connection refused",
            }
        return {
            "status": "ok",
            "enabled": True,
            "ready": True,
            "url": "http://localhost:6333",
            "collection": self.collection,
            "collection_exists": True,
            "vector_size": self.vector_size,
            "collections": [self.collection],
        }

    async def ensure_collection(self) -> dict[str, Any]:
        if not self.enabled:
            raise store_module.QdrantStoreError("qdrant_disabled", "disabled")
        return {
            "collection": self.collection,
            "created": False,
            "exists": True,
            "points_count": len(self.points),
            "vector_size": self.vector_size,
            "distance": "Cosine",
        }

    async def upsert_points(self, points: list[dict[str, Any]]) -> dict[str, Any]:
        ids = []
        for point in points:
            self.points[point["id"]] = point
            ids.append(point["id"])
        return {"upserted": len(ids), "collection": self.collection, "ids": ids}

    async def search(self, vector: list[float], *, top_k: int = 4, score_threshold: float | None = None) -> dict[str, Any]:
        results = [
            {
                "id": pid,
                "score": 0.99,
                "title": point.get("title"),
                "category": point.get("category"),
                "metadata": point.get("metadata") or {},
                "payload": point,
            }
            for pid, point in list(self.points.items())[:top_k]
        ]
        return {
            "collection": self.collection,
            "metric": "cosine",
            "top_k": top_k,
            "count": len(results),
            "results": results,
        }

    async def list_points(self, *, limit: int = 100) -> dict[str, Any]:
        points = [
            {
                "id": pid,
                "title": p.get("title"),
                "category": p.get("category"),
                "vector": p.get("vector") or [],
                "metadata": p.get("metadata") or {},
                "payload": p,
            }
            for pid, p in list(self.points.items())[:limit]
        ]
        return {"collection": self.collection, "count": len(points), "points": points}

    async def delete_point(self, document_id: str) -> dict[str, Any]:
        self.points.pop(document_id, None)
        return {"deleted": True, "id": document_id, "collection": self.collection}


@pytest.fixture
def fake_store(monkeypatch: pytest.MonkeyPatch, authenticated_user: None) -> FakeStore:
    store = FakeStore()
    monkeypatch.setattr(vector_router, "get_qdrant_store", lambda: store)
    monkeypatch.setenv("QDRANT_ENABLED", "true")
    get_settings.cache_clear()
    yield store
    get_settings.cache_clear()
    store_module.reset_qdrant_store_for_tests()


def test_vector_health_ok(fake_store: FakeStore) -> None:
    response = client.get("/api/v1/vector/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["backend"] == "qdrant"
    assert body["feature"] == "phase1-qdrant"


def test_vector_ready_503_when_down(monkeypatch: pytest.MonkeyPatch) -> None:
    store = FakeStore(ready=False)
    monkeypatch.setattr(vector_router, "get_qdrant_store", lambda: store)
    monkeypatch.setenv("QDRANT_ENABLED", "true")
    get_settings.cache_clear()
    try:
        response = client.get("/api/v1/vector/ready")
        assert response.status_code == 503
    finally:
        get_settings.cache_clear()
        store_module.reset_qdrant_store_for_tests()


def test_vector_data_operations_require_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_dev_bypass", False)
    response = client.post("/api/v1/vector/collections/ensure")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "auth_required"


def test_vector_rejects_oversized_auxiliary_payload(authenticated_user: None) -> None:
    response = client.post(
        "/api/v1/vector/points",
        json={
            "points": [
                {
                    "id": "VEC-TOO-LARGE",
                    "vector": [0.1] * 8,
                    "metadata": {"description": "x" * (16 * 1024)},
                }
            ]
        },
    )
    assert response.status_code == 422


def test_ensure_upsert_search(fake_store: FakeStore) -> None:
    ensure = client.post("/api/v1/vector/collections/ensure")
    assert ensure.status_code == 200
    assert ensure.json()["success"] is True

    upsert = client.post(
        "/api/v1/vector/points",
        json={
            "points": [
                {
                    "id": "VEC-TEST01",
                    "title": "Test Node",
                    "category": "strategy",
                    "vector": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
                    "metadata": {"description": "smoke"},
                }
            ]
        },
    )
    assert upsert.status_code == 200
    assert upsert.json()["upserted"] == 1

    search = client.post(
        "/api/v1/vector/search",
        json={"vector": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8], "top_k": 3, "metric": "cosine"},
    )
    assert search.status_code == 200
    body = search.json()
    assert body["success"] is True
    assert body["count"] >= 1
    assert body["results"][0]["id"] == "VEC-TEST01"
