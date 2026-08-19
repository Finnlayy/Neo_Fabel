import pytest

from backend.app.trading.autonomy import AutonomyLevel, require_autonomy


def test_require_autonomy_success() -> None:
    # Equal level
    require_autonomy(AutonomyLevel.PAPER, AutonomyLevel.PAPER)

    # Higher level
    require_autonomy(AutonomyLevel.SUPERVISED, AutonomyLevel.PAPER)
    require_autonomy(AutonomyLevel.FUND_MANAGEMENT, AutonomyLevel.AUTONOMOUS)


def test_require_autonomy_failure() -> None:
    # Lower level
    with pytest.raises(PermissionError, match="autonomy level 2 is below required level 3"):
        require_autonomy(AutonomyLevel.PAPER, AutonomyLevel.SUPERVISED)

    with pytest.raises(PermissionError, match="autonomy level 1 is below required level 5"):
        require_autonomy(AutonomyLevel.READ_ONLY, AutonomyLevel.FUND_MANAGEMENT)
