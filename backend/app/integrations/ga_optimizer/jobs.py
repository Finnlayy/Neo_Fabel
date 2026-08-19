"""In-memory + disk-persisted GA job registry."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.settings import Settings, get_settings

from .engine import run_ga_optimize
from .market_data import load_universe_packs
from .pine_export import export_pines_from_payload

logger = logging.getLogger("neo_fabel.ga.jobs")


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _coalesce(value: Any, default: Any) -> Any:
    return default if value is None else value


def default_ga_runs_dir(settings: Settings | None = None) -> Path:
    s = settings or get_settings()
    if s.ga_data_dir:
        return Path(s.ga_data_dir)
    return Path(__file__).resolve().parents[3] / "data" / "ga_runs"


def default_ga_cache_dir(settings: Settings | None = None) -> Path:
    s = settings or get_settings()
    if s.ga_cache_dir:
        return Path(s.ga_cache_dir)
    return Path(__file__).resolve().parents[3] / "data" / "ga_cache"


class GaJobRegistry:
    """Tracks GA optimize jobs; at most GA_MAX_CONCURRENT_JOBS run at once."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._sem: asyncio.Semaphore | None = None
        self._tasks: dict[str, asyncio.Task[Any]] = {}

    def _ensure_sem(self, settings: Settings) -> asyncio.Semaphore:
        if self._sem is None:
            self._sem = asyncio.Semaphore(max(1, settings.ga_max_concurrent_jobs))
        return self._sem

    def _run_dir(self, run_id: str, settings: Settings) -> Path:
        root = default_ga_runs_dir(settings)
        root.mkdir(parents=True, exist_ok=True)
        path = root / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _persist(self, run_id: str, settings: Settings) -> None:
        with self._lock:
            job = dict(self._jobs.get(run_id) or {})
        if not job:
            return
        run_dir = self._run_dir(run_id, settings)
        (run_dir / "job.json").write_text(json.dumps(job, indent=2, default=str), encoding="utf-8")
        if job.get("results"):
            results = dict(job["results"])
            report = results.pop("report_md", None)
            (run_dir / "results.json").write_text(
                json.dumps(results, indent=2, default=str), encoding="utf-8"
            )
            if report:
                (run_dir / "report.md").write_text(str(report), encoding="utf-8")

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(run_id)
            if job:
                return dict(job)
        settings = get_settings()
        path = default_ga_runs_dir(settings) / run_id / "job.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                with self._lock:
                    self._jobs[run_id] = data
                return dict(data)
            except Exception:  # noqa: BLE001
                return None
        return None

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = [dict(j) for j in self._jobs.values()]
        settings = get_settings()
        root = default_ga_runs_dir(settings)
        if root.exists():
            known = {r.get("runId") for r in rows}
            for child in root.iterdir():
                if not child.is_dir() or child.name in known:
                    continue
                job_path = child / "job.json"
                if job_path.exists():
                    try:
                        rows.append(json.loads(job_path.read_text(encoding="utf-8")))
                    except Exception:  # noqa: BLE001
                        continue
        rows.sort(key=lambda r: str(r.get("createdAt") or ""), reverse=True)
        return rows[:limit]

    def update(self, run_id: str, **fields: Any) -> None:
        settings = get_settings()
        with self._lock:
            job = self._jobs.get(run_id)
            if not job:
                return
            job.update(fields)
            job["updatedAt"] = _utcnow()
        self._persist(run_id, settings)

    async def start_optimize(self, request: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        if not settings.ga_optimizer_enabled:
            raise RuntimeError("GA optimizer is disabled (GA_OPTIMIZER_ENABLED=false)")

        run_id = uuid4().hex[:12]
        job: dict[str, Any] = {
            "runId": run_id,
            "status": "queued",
            "createdAt": _utcnow(),
            "updatedAt": _utcnow(),
            "request": request,
            "progress": {"generation": 0, "generations": request.get("generations")},
            "top3": [],
            "results": None,
            "error": None,
        }
        with self._lock:
            self._jobs[run_id] = job
        self._persist(run_id, settings)

        sem = self._ensure_sem(settings)

        async def _runner() -> None:
            async with sem:
                self.update(run_id, status="running")
                try:
                    result = await asyncio.to_thread(self._run_sync, run_id, request, settings)
                    self.update(
                        run_id,
                        status="completed",
                        results=result,
                        top3=result.get("top3") or [],
                        progress={
                            "generation": request.get("generations"),
                            "generations": request.get("generations"),
                            "status": "completed",
                        },
                    )
                except Exception as exc:
                    logger.exception("GA job %s failed", run_id)
                    self.update(run_id, status="failed", error=str(exc))

        self._tasks[run_id] = asyncio.create_task(_runner())
        return {"runId": run_id, "status": "queued"}

    def _run_sync(self, run_id: str, request: dict[str, Any], settings: Settings) -> dict[str, Any]:
        cache_dir = default_ga_cache_dir(settings)
        cache_dir.mkdir(parents=True, exist_ok=True)
        market_source = request.get("market_source") or settings.ga_market_source
        max_symbols = int(_coalesce(request.get("max_symbols"), settings.ga_max_symbols))
        lookback = int(_coalesce(request.get("lookback_bars"), settings.ga_lookback_bars))
        packs, symbols = load_universe_packs(
            cache_dir=cache_dir,
            market_source=market_source,
            max_symbols=max_symbols,
            lookback_bars=lookback,
            symbols=request.get("symbols"),
        )

        def on_progress(info: dict[str, Any]) -> None:
            self.update(run_id, progress=info, top3=info.get("top3") or [])

        return run_ga_optimize(
            packs,
            symbols,
            population=int(_coalesce(request.get("population"), settings.ga_default_population)),
            generations=int(_coalesce(request.get("generations"), settings.ga_default_generations)),
            elite=int(_coalesce(request.get("elite"), 3)),
            mutation_rate=float(_coalesce(request.get("mutation_rate"), 0.05)),
            mutation_strength=float(_coalesce(request.get("mutation_strength"), 0.40)),
            crossover_threshold=float(_coalesce(request.get("crossover_threshold"), 0.20)),
            train_ratio=float(_coalesce(request.get("train_ratio"), settings.ga_train_ratio)),
            fee_r=float(_coalesce(request.get("fee_r"), settings.ga_fee_r)),
            lookback_bars=lookback,
            max_symbols=max_symbols,
            seed=int(_coalesce(request.get("seed"), 42)),
            on_progress=on_progress,
        )

    def export_pine(self, request: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        payload = request.get("results")
        run_id = request.get("runId")
        if payload is None and run_id:
            job = self.get(run_id)
            if not job:
                raise KeyError(f"Unknown runId: {run_id}")
            payload = job.get("results")
            if not payload:
                path = default_ga_runs_dir(settings) / run_id / "results.json"
                if path.exists():
                    payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Provide results payload or a completed runId")

        out_run = run_id or uuid4().hex[:12]
        out_dir = self._run_dir(out_run, settings) / "pines"
        written = export_pines_from_payload(
            payload,
            out_dir,
            template_id=request.get("template_id") or "eth_glintnews_pionex_v6",
            limit=int(request.get("limit") or 3),
            target_symbol=request.get("target_symbol") or "ETH/USDT",
            tf_high=request.get("tf_high") or "48",
            tf_mid=request.get("tf_mid") or "12",
            tf_low=request.get("tf_low") or "3",
        )
        return {"runId": out_run, "files": written, "outputDir": str(out_dir)}


ga_jobs = GaJobRegistry()
