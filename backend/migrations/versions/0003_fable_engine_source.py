"""Allow 'fable_engine' as signal_events.source (internal Grid/DCA generators).

Revision ID: 0003_fable_engine_source
Revises: 0002_signal_routes

Status column stays constraint-free (String(32)); the new terminal status
'dry_run_recorded' needs no DDL. Downgrade fails if fable_engine rows exist —
delete them first (research data only).
"""

from alembic import op


revision = "0003_fable_engine_source"
down_revision = "0002_signal_routes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_signal_events_source", "signal_events", type_="check")
    op.create_check_constraint(
        "ck_signal_events_source",
        "signal_events",
        "source IN ('tradingview', 'mcp', 'fable_engine')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_signal_events_source", "signal_events", type_="check")
    op.create_check_constraint(
        "ck_signal_events_source",
        "signal_events",
        "source IN ('tradingview', 'mcp')",
    )
