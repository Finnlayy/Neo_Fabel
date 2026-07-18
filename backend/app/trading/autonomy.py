from enum import IntEnum


class AutonomyLevel(IntEnum):
    """Kraken agent autonomy levels (see kraken-autonomy-levels skill)."""

    READ_ONLY = 1
    PAPER = 2
    SUPERVISED = 3
    AUTONOMOUS = 4
    FUND_MANAGEMENT = 5


def require_autonomy(current: AutonomyLevel, minimum: AutonomyLevel) -> None:
    """Raise if the configured autonomy level is below the required minimum."""
    if current < minimum:
        raise PermissionError(
            f"autonomy level {int(current)} is below required level {int(minimum)}"
        )
