"""ONNX train / export / infer / API (optional deps)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.auth import require_user
from backend.app.integrations.onnx.runtime import onnx_deps_available
from backend.app.main import app

pytestmark = pytest.mark.skipif(not onnx_deps_available(), reason="pip install -e '.[onnx]'")

client = TestClient(app)


@pytest.fixture
def authenticated_user() -> None:
    app.dependency_overrides[require_user] = lambda: {
        "uid": "onnx-test-user",
        "email_verified": True,
        "firebase": {"sign_in_provider": "google.com"},
    }
    yield
    app.dependency_overrides.pop(require_user, None)


def test_train_export_infer_roundtrip(tmp_path, monkeypatch, authenticated_user) -> None:
    from backend.app.integrations.onnx import paths as onnx_paths
    from backend.app.integrations.onnx.graph_summary import summarize_graph
    from backend.app.integrations.onnx.infer import run_infer
    from backend.app.integrations.onnx.manifest import get_active, set_active
    from backend.app.integrations.onnx.predictor import predict
    from backend.app.integrations.onnx.train import train_and_export

    monkeypatch.setattr(onnx_paths, "ONNX_DATA_DIR", tmp_path)
    monkeypatch.setattr(onnx_paths, "ensure_onnx_data_dir", lambda: tmp_path)

    meta = train_and_export(model_id="model4", symbol="BTCUSD", limit=200, source="test", seed=7)
    assert meta["id"] == "model4"
    assert (tmp_path / "model4.onnx").exists()
    assert meta["input_name"] == "lstm_input"
    assert meta["input_shape"] == [1, 10, 4]
    assert meta["feature_set"] == "ohlc_v1"
    assert meta["checksum"]
    assert meta["version"]
    checksum1 = meta["checksum"]

    graph = summarize_graph("model4")
    assert graph["ops"] == ["Flatten", "Gemm"]
    assert graph["weight_fingerprint"]
    fp1 = graph["weight_fingerprint"]

    set_active("model4")
    assert get_active() == "model4"

    out = run_infer(model_id="model4", symbol="BTCUSD")
    assert out["onnxModel"] == "model4.onnx"
    assert out["direction"] in {"UP", "DOWN", "STABLE"}
    assert "prediction" in out

    pred = predict(model_id=None, symbol="BTCUSD", allow_fallback=True)
    assert pred["model_id"] == "model4"
    assert pred["provider"] in {"onnxruntime", "mean_fallback"}

    meta2 = train_and_export(model_id="model4", symbol="ETHUSD", limit=220, source="test", seed=99)
    assert meta2["checksum"] != checksum1
    graph2 = summarize_graph("model4")
    assert graph2["weight_fingerprint"] != fp1


def test_predictor_mean_fallback_without_ort(tmp_path, monkeypatch) -> None:
    from backend.app.integrations.onnx import paths as onnx_paths
    from backend.app.integrations.onnx import predictor as pred_mod
    from backend.app.integrations.onnx.train import train_and_export

    monkeypatch.setattr(onnx_paths, "ONNX_DATA_DIR", tmp_path)
    monkeypatch.setattr(onnx_paths, "ensure_onnx_data_dir", lambda: tmp_path)
    train_and_export(model_id="model4", symbol="BTCUSD", limit=120, source="test", seed=1)
    monkeypatch.setattr(pred_mod, "onnx_deps_available", lambda: False)
    out = pred_mod.predict(model_id="model4", symbol="BTCUSD", allow_fallback=True)
    assert out["provider"] == "mean_fallback"
    assert out["syncStatus"] == "MEAN FALLBACK"


def test_onnx_api_status_and_train(authenticated_user) -> None:
    status = client.get("/api/v1/onnx/status")
    assert status.status_code == 200
    body = status.json()
    assert body["runtime_available"] is True
    assert body["model_count"] >= 1
    assert body.get("active_model_id")
    assert body.get("feature_set") == "ohlc_v1"

    models = client.get("/api/v1/onnx/models")
    assert models.status_code == 200
    assert len(models.json()["models"]) >= 1

    active = client.post("/api/v1/onnx/models/active", json={"model_id": "model4"})
    assert active.status_code == 200
    assert active.json()["active_model_id"] == "model4"

    graph = client.get("/api/v1/onnx/models/model4/graph")
    assert graph.status_code == 200
    g = graph.json()
    assert "weight_fingerprint" in g
    assert g["ops"] == ["Flatten", "Gemm"]

    train = client.post(
        "/api/v1/onnx/train",
        json={"model_id": "model4", "symbol": "ETHUSD", "limit": 180, "seed": 3},
    )
    assert train.status_code == 200
    assert train.json()["status"] == "completed"
    assert train.json().get("checksum")

    infer = client.post(
        "/api/v1/onnx/infer",
        json={"model_id": "model4", "symbol": "ETHUSD"},
    )
    assert infer.status_code == 200
    assert infer.json()["provider"] == "onnxruntime"

    static = client.get("/static/onnx/model4.onnx")
    assert static.status_code == 200
    assert len(static.content) > 32


def test_onnx_upload_roundtrip(tmp_path, monkeypatch, authenticated_user) -> None:
    from backend.app.integrations.onnx import paths as onnx_paths
    from backend.app.integrations.onnx.train import train_and_export

    monkeypatch.setattr(onnx_paths, "ONNX_DATA_DIR", tmp_path)
    monkeypatch.setattr(onnx_paths, "ensure_onnx_data_dir", lambda: tmp_path)

    train_and_export(model_id="model4", symbol="BTCUSD", limit=100, source="test", seed=2)
    raw = (tmp_path / "model4.onnx").read_bytes()

    # Point API paths at tmp via monkeypatch already; ensure seeds use same dir
    up = client.post(
        "/api/v1/onnx/models/upload",
        files={"file": ("custom_lstm.onnx", raw, "application/octet-stream")},
        data={"model_id": "custom_lstm", "make_active": "true"},
    )
    assert up.status_code == 200, up.text
    body = up.json()
    assert body["status"] == "uploaded"
    assert body["meta"]["id"] == "custom_lstm"
    assert body["meta"]["source"] == "upload"
    assert body["active_model_id"] == "custom_lstm"
    assert (tmp_path / "custom_lstm.onnx").exists()

    bad = client.post(
        "/api/v1/onnx/models/upload",
        files={"file": ("nope.onnx", b"not-an-onnx", "application/octet-stream")},
    )
    assert bad.status_code == 400
