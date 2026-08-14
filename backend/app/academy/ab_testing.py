"""Prompt A/B testing store."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from backend.app.academy.paths import ACADEMY_DATA_DIR, ensure_academy_data_dir
from backend.app.academy.schemas import ABTest

AB_TESTS_FILE = ACADEMY_DATA_DIR / "ab_tests.json"


class ABTestingService:
    def __init__(self) -> None:
        self._tests: dict[str, ABTest] = {}
        self._ensure_files()
        self.load_tests()

    def _ensure_files(self) -> None:
        ensure_academy_data_dir()
        if not AB_TESTS_FILE.exists():
            with open(AB_TESTS_FILE, "w", encoding="utf-8") as handle:
                json.dump([], handle)

    def load_tests(self) -> None:
        if AB_TESTS_FILE.exists():
            try:
                with open(AB_TESTS_FILE, encoding="utf-8") as handle:
                    data = json.load(handle)
                    for item in data:
                        test = ABTest(**item)
                        self._tests[test.test_id] = test
            except Exception as exc:  # noqa: BLE001
                print(f"Error loading AB tests: {exc}")

    def save_tests(self) -> None:
        try:
            ensure_academy_data_dir()
            with open(AB_TESTS_FILE, "w", encoding="utf-8") as handle:
                json.dump([t.model_dump() for t in self._tests.values()], handle, indent=2)
        except Exception as exc:  # noqa: BLE001
            print(f"Error saving AB tests: {exc}")

    def start_test(self, scout_name: str, variant_a: str, variant_b: str) -> ABTest:
        test = ABTest(
            scout_name=scout_name,
            variant_a_version=variant_a,
            variant_b_version=variant_b,
        )
        self._tests[test.test_id] = test
        self.save_tests()
        return test

    def record_call(self, test_id: str, is_variant_a: bool, is_correct: bool) -> None:
        test = self._tests.get(test_id)
        if not test or test.status != "running":
            return
        if is_variant_a:
            test.calls_a += 1
            if is_correct:
                test.correct_a += 1
        else:
            test.calls_b += 1
            if is_correct:
                test.correct_b += 1
        self.save_tests()

    def conclude_test(self, test_id: str) -> ABTest | None:
        test = self._tests.get(test_id)
        if not test:
            return None
        acc_a = test.correct_a / test.calls_a if test.calls_a > 0 else 0
        acc_b = test.correct_b / test.calls_b if test.calls_b > 0 else 0
        test.winner_version = test.variant_a_version if acc_a >= acc_b else test.variant_b_version
        test.status = "concluded"
        test.concluded_at = datetime.now(UTC).isoformat()
        self.save_tests()
        return test

    def get_all(self) -> list[ABTest]:
        return list(self._tests.values())


ab_testing = ABTestingService()
