"""Scout identity store, badges, career JSONL."""

from __future__ import annotations

import json
from collections import deque

import aiofiles

from backend.app.academy.agent_defs import NEO_AGENT_DEFINITIONS
from backend.app.academy.paths import ACADEMY_DATA_DIR, ensure_academy_data_dir
from backend.app.academy.schemas import Badge, CareerEntry, ScoutIdentity

CAREER_LOG_FILE = ACADEMY_DATA_DIR / "agent_careers.jsonl"
REGISTRY_FILE = ACADEMY_DATA_DIR / "agent_registry.json"


class AgentRegistryService:
    def __init__(self) -> None:
        self._identities: dict[str, ScoutIdentity] = {}
        self._ensure_files()
        self.load_registry()

    def _ensure_files(self) -> None:
        ensure_academy_data_dir()
        if not CAREER_LOG_FILE.exists():
            CAREER_LOG_FILE.touch()

    def load_registry(self) -> None:
        if REGISTRY_FILE.exists():
            try:
                with open(REGISTRY_FILE, encoding="utf-8") as handle:
                    data = json.load(handle)
                    for scout_data in data:
                        identity = ScoutIdentity(**scout_data)
                        self._identities[identity.name] = identity
            except Exception as exc:  # noqa: BLE001
                print(f"Error loading agent registry: {exc}")

        for default in NEO_AGENT_DEFINITIONS:
            if default.name not in self._identities:
                self._identities[default.name] = ScoutIdentity(
                    name=default.name,
                    archetype=default.archetype,
                    personality_vector=dict(default.personality_vector),
                )
        self.save_registry()

    def save_registry(self) -> None:
        try:
            ensure_academy_data_dir()
            with open(REGISTRY_FILE, "w", encoding="utf-8") as handle:
                json.dump([i.model_dump() for i in self._identities.values()], handle, indent=2)
        except Exception as exc:  # noqa: BLE001
            print(f"Error saving agent registry: {exc}")

    def get_identity(self, name: str) -> ScoutIdentity | None:
        return self._identities.get(name)

    def get_all_identities(self) -> list[ScoutIdentity]:
        return list(self._identities.values())

    def _next_deployed_name(self) -> str:
        index = len(self._identities) + 1
        while f"ui-agent-{index}" in self._identities:
            index += 1
        return f"ui-agent-{index}"

    def deploy_identity(
        self,
        name: str | None = None,
        archetype: str = "Analyst",
        personality_vector: dict[str, float] | None = None,
        specialization_symbols: list[str] | None = None,
    ) -> ScoutIdentity:
        agent_name = (name or "").strip() or self._next_deployed_name()
        if agent_name in self._identities:
            raise ValueError(f"Agent {agent_name} already exists")

        identity = ScoutIdentity(
            name=agent_name,
            archetype=archetype,
            born_from="ui_deploy",
            specialization_symbols=specialization_symbols or [],
            personality_vector=personality_vector or {},
        )
        self._identities[identity.name] = identity
        self.save_registry()
        return identity

    async def log_career_event(
        self,
        entry: CareerEntry,
        *,
        save_registry: bool = True,
        write_log: bool = True,
    ) -> None:
        ident = self._identities.get(entry.scout_name)
        if ident:
            if entry.event_type == "prediction_result":
                ident.total_calls += 1
                is_correct = entry.details.get("is_correct", False)
                if is_correct:
                    ident.correct_calls += 1
                    ident.current_streak += 1
                else:
                    ident.current_streak = 0
                ident.accuracy = ident.correct_calls / ident.total_calls if ident.total_calls > 0 else 0.0
                await self._check_badges(
                    ident, entry, save_registry=save_registry, write_log=write_log
                )
            elif entry.event_type == "badge_earned":
                badge_data = entry.details.get("badge", {})
                if badge_data:
                    ident.badges.append(Badge(**badge_data))

            if save_registry:
                self.save_registry()

        if not write_log:
            return

        async with aiofiles.open(CAREER_LOG_FILE, "a", encoding="utf-8") as handle:
            await handle.write(entry.model_dump_json() + "\n")

    async def _check_badges(
        self,
        ident: ScoutIdentity,
        entry: CareerEntry,
        *,
        save_registry: bool = True,
        write_log: bool = True,
    ) -> None:
        del entry  # unused; kept for Jules signature parity
        existing = {b.name for b in ident.badges}
        new_badges: list[Badge] = []
        if ident.total_calls >= 10 and "Apprentice" not in existing:
            new_badges.append(Badge(name="Apprentice", description="10+ Calls", icon="A"))
        if ident.total_calls >= 50 and ident.accuracy >= 0.6 and "Adept" not in existing:
            new_badges.append(Badge(name="Adept", description="50+ Calls, 60%+ Accuracy", icon="B"))
        if ident.total_calls >= 100 and ident.accuracy >= 0.7 and "Expert" not in existing:
            new_badges.append(Badge(name="Expert", description="100+ Calls, 70%+ Accuracy", icon="C"))
        if ident.current_streak >= 10 and "Streak" not in existing:
            new_badges.append(Badge(name="Streak", description="10 correct calls in a row", icon="S"))

        for badge in new_badges:
            await self.log_career_event(
                CareerEntry(
                    scout_name=ident.name,
                    event_type="badge_earned",
                    details={"badge": badge.model_dump()},
                ),
                save_registry=save_registry,
                write_log=write_log,
            )

    def get_career_log(self, scout_name: str) -> list[CareerEntry]:
        entries: list[CareerEntry] = []
        if not CAREER_LOG_FILE.exists():
            return entries
        try:
            with open(CAREER_LOG_FILE, encoding="utf-8") as handle:
                for line in handle:
                    if scout_name not in line or not line.strip():
                        continue
                    if f'"scout_name":"{scout_name}"' not in line and f'"scout_name": "{scout_name}"' not in line:
                        continue
                    data = json.loads(line)
                    if data.get("scout_name") == scout_name:
                        entries.append(CareerEntry(**data))
        except Exception as exc:  # noqa: BLE001
            print(f"Error reading career log: {exc}")
        return entries

    def get_recent_career_events(
        self,
        *,
        limit: int = 50,
        event_type: str | None = None,
    ) -> list[CareerEntry]:
        entries: list[CareerEntry] = []
        if not CAREER_LOG_FILE.exists():
            return entries
        try:
            line_deque: deque[str] = deque(maxlen=limit)
            with open(CAREER_LOG_FILE, encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    if event_type and event_type not in line:
                        continue
                    line_deque.append(line)
            for line in reversed(line_deque):
                data = json.loads(line)
                if event_type and data.get("event_type") != event_type:
                    continue
                entries.append(CareerEntry(**data))
                if len(entries) >= limit:
                    break
        except Exception as exc:  # noqa: BLE001
            print(f"Error reading recent career events: {exc}")
        return entries


agent_registry = AgentRegistryService()
