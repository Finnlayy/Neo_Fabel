"""Per-agent curriculum progress (Beginner→Master)."""

from __future__ import annotations

import json

from backend.app.academy.paths import ACADEMY_DATA_DIR, ensure_academy_data_dir
from backend.app.academy.schemas import CurriculumProgress

CURRICULUM_FILE = ACADEMY_DATA_DIR / "curriculum_progress.json"


class AcademyCurriculumService:
    def __init__(self) -> None:
        self._progress: dict[str, CurriculumProgress] = {}
        self._ensure_files()
        self.load_progress()

    def _ensure_files(self) -> None:
        ensure_academy_data_dir()
        if not CURRICULUM_FILE.exists():
            with open(CURRICULUM_FILE, "w", encoding="utf-8") as handle:
                json.dump([], handle)

    def load_progress(self) -> None:
        if CURRICULUM_FILE.exists():
            try:
                with open(CURRICULUM_FILE, encoding="utf-8") as handle:
                    data = json.load(handle)
                    for item in data:
                        cp = CurriculumProgress(**item)
                        self._progress[f"{cp.scout_name}_{cp.curriculum_level}"] = cp
            except Exception as exc:  # noqa: BLE001
                print(f"Error loading curriculum progress: {exc}")

    def save_progress(self) -> None:
        try:
            ensure_academy_data_dir()
            with open(CURRICULUM_FILE, "w", encoding="utf-8") as handle:
                json.dump([cp.model_dump() for cp in self._progress.values()], handle, indent=2)
        except Exception as exc:  # noqa: BLE001
            print(f"Error saving curriculum progress: {exc}")

    def get_progress(
        self, scout_name: str, level: str = "Beginner", *, save_new: bool = True
    ) -> CurriculumProgress:
        key = f"{scout_name}_{level}"
        if key not in self._progress:
            req = {"Beginner": 10, "Intermediate": 25, "Advanced": 50, "Master": 100}.get(level, 10)
            cp = CurriculumProgress(
                scout_name=scout_name,
                curriculum_level=level,
                required_drills=req,
            )
            self._progress[key] = cp
            if save_new:
                self.save_progress()
        return self._progress[key]

    def record_drill_result(
        self,
        scout_name: str,
        level: str,
        is_correct: bool,
        confidence: float,
        *,
        save: bool = True,
    ) -> None:
        cp = self.get_progress(scout_name, level, save_new=save)
        cp.completed_drills += 1
        if is_correct:
            cp.passed_drills += 1
        cp.average_confidence = cp.average_confidence + (
            (confidence - cp.average_confidence) / cp.completed_drills
        )
        if save:
            self.save_progress()

    def get_all_for_scout(self, scout_name: str) -> list[CurriculumProgress]:
        return [cp for cp in self._progress.values() if cp.scout_name == scout_name]


academy_curriculum = AcademyCurriculumService()
