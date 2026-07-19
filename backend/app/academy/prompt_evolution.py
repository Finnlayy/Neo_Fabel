"""Prompt version registry."""

from __future__ import annotations

import json
from typing import Optional

from backend.app.academy.agent_defs import NEO_AGENT_NAMES
from backend.app.academy.paths import ACADEMY_DATA_DIR, ensure_academy_data_dir
from backend.app.academy.schemas import PromptVersion

PROMPT_REGISTRY_FILE = ACADEMY_DATA_DIR / "prompt_registry.json"


class PromptEvolutionService:
    def __init__(self) -> None:
        self._versions: dict[str, PromptVersion] = {}
        self._ensure_files()
        self.load_registry()

    def _ensure_files(self) -> None:
        ensure_academy_data_dir()
        if not PROMPT_REGISTRY_FILE.exists():
            with open(PROMPT_REGISTRY_FILE, "w", encoding="utf-8") as handle:
                json.dump([], handle)

    def load_registry(self) -> None:
        if PROMPT_REGISTRY_FILE.exists():
            try:
                with open(PROMPT_REGISTRY_FILE, encoding="utf-8") as handle:
                    data = json.load(handle)
                    for item in data:
                        pv = PromptVersion(**item)
                        self._versions[pv.version_id] = pv
            except Exception as exc:  # noqa: BLE001
                print(f"Error loading prompt registry: {exc}")

        if not self._versions:
            for scout in NEO_AGENT_NAMES:
                self.create_version(
                    scout,
                    f"{scout}_v1_base",
                    f"You are the {scout} review agent.",
                    change_summary="Base version",
                )

    def save_registry(self) -> None:
        try:
            ensure_academy_data_dir()
            with open(PROMPT_REGISTRY_FILE, "w", encoding="utf-8") as handle:
                json.dump([v.model_dump() for v in self._versions.values()], handle, indent=2)
        except Exception as exc:  # noqa: BLE001
            print(f"Error saving prompt registry: {exc}")

    def create_version(
        self,
        scout_name: str,
        version_id: str,
        prompt_text: str,
        parent_version: Optional[str] = None,
        change_summary: str = "",
    ) -> PromptVersion:
        pv = PromptVersion(
            version_id=version_id,
            scout_name=scout_name,
            prompt_text=prompt_text,
            parent_version=parent_version,
            change_summary=change_summary,
        )
        self._versions[version_id] = pv
        self.save_registry()
        return pv

    def get_version(self, version_id: str) -> Optional[PromptVersion]:
        return self._versions.get(version_id)

    def get_all_for_scout(self, scout_name: str) -> list[PromptVersion]:
        versions = [v for v in self._versions.values() if v.scout_name == scout_name]
        versions.sort(key=lambda x: x.created_at, reverse=True)
        return versions


prompt_evolution = PromptEvolutionService()
