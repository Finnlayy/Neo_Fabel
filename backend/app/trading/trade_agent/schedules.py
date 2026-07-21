"""Schedule definitions — Berlin-friendly slots mirrored from TradeAgent bats."""

from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")
ET = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class ScheduleSlot:
    """Local wall-clock slot (hour, minute) in the given timezone."""

    job_id: str
    hour: int
    minute: int
    tz_name: str
    description: str

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.tz_name)


# From TradeAgent schedule_*.bat + EVENT_DRIVEN_TRADING.md (ET entry scans),
# expressed as Neo defaults (Berlin for Windows Task Scheduler bats; ET for crypto/US).
DEFAULT_SLOTS: tuple[ScheduleSlot, ...] = (
    ScheduleSlot("market_scan_morning", 7, 0, "Europe/Berlin", "Pre-market / morning momentum scan"),
    ScheduleSlot("market_scan_preopen", 15, 0, "Europe/Berlin", "Pre-open US session scan"),
    ScheduleSlot("market_scan_hours", 16, 0, "Europe/Berlin", "Market-hours scan (10:00 ET)"),
    ScheduleSlot("label_trades", 18, 0, "Europe/Berlin", "Label paper fills for ML (12:00 ET)"),
    ScheduleSlot("optimizer_night", 2, 30, "Europe/Berlin", "Overnight GA / param optimizer"),
    # Event-driven ET entry windows (crypto 24/7 still uses these as priority ticks)
    ScheduleSlot("et_gap_momentum", 9, 35, "America/New_York", "Gap & morning momentum (ET)"),
    ScheduleSlot("et_post_open", 10, 30, "America/New_York", "Post-open continuation (ET)"),
    ScheduleSlot("et_midday", 12, 0, "America/New_York", "Midday breakouts (ET)"),
    ScheduleSlot("et_afternoon", 14, 0, "America/New_York", "Afternoon setup (ET)"),
    ScheduleSlot("et_power_hour", 15, 45, "America/New_York", "Power hour momentum (ET)"),
)

# Exit / positions watchdog cadence (seconds) during "session" — mirrors TradeAgent 5m exits.
POSITIONS_WATCHDOG_SECONDS = 300
