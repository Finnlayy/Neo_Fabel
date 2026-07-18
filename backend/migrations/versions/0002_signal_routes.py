"""Signal routes, events, jobs, evaluations, audit; paper intent source fields.

Revision ID: 0002_signal_routes
Revises: 0001_paper_order_intents
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_signal_routes"
down_revision = "0001_paper_order_intents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "paper_order_intents",
        sa.Column("source", sa.String(length=16), nullable=False, server_default="manual"),
    )
    op.add_column("paper_order_intents", sa.Column("source_ref", sa.String(length=36), nullable=True))
    op.create_check_constraint(
        "ck_paper_order_intents_source",
        "paper_order_intents",
        "source IN ('manual', 'signal')",
    )
    op.create_index(
        "uq_paper_order_intents_signal_source_ref",
        "paper_order_intents",
        ["source_ref"],
        unique=True,
        postgresql_where=sa.text("source = 'signal' AND source_ref IS NOT NULL"),
    )

    op.create_table(
        "signal_routes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_uid", sa.String(length=128), nullable=False),
        sa.Column("public_route_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("strategy_id", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("execution_target", sa.String(length=32), nullable=False),
        sa.Column("pair_allowlist", sa.Text(), nullable=False),
        sa.Column("max_volume", sa.Numeric(precision=24, scale=12), nullable=False),
        sa.Column("max_notional", sa.Numeric(precision=24, scale=12), nullable=True),
        sa.Column("allowed_order_types", sa.String(length=64), nullable=False),
        sa.Column("max_event_age_seconds", sa.Integer(), nullable=False),
        sa.Column("max_rate_per_minute", sa.Integer(), nullable=False),
        sa.Column("max_backlog", sa.Integer(), nullable=False),
        sa.Column("max_open_exposure", sa.Numeric(precision=24, scale=12), nullable=True),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("mode IN ('bypass_ai', 'advisory')", name="ck_signal_routes_mode"),
        sa.CheckConstraint("execution_target = 'kraken_paper'", name="ck_signal_routes_target"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_route_key", name="uq_signal_routes_public_key"),
    )
    op.create_index("ix_signal_routes_owner_user_uid", "signal_routes", ["owner_user_uid"])

    op.create_table(
        "signal_route_credentials",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("route_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("digest", sa.String(length=128), nullable=False),
        sa.Column("pepper_version", sa.String(length=16), nullable=False),
        sa.Column("display_prefix", sa.String(length=16), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('tradingview_secret', 'mcp_bearer')", name="ck_signal_credentials_kind"),
        sa.ForeignKeyConstraint(["route_id"], ["signal_routes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signal_route_credentials_route_id", "signal_route_credentials", ["route_id"])

    op.create_table(
        "signal_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("route_id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("credential_id", sa.String(length=36), nullable=True),
        sa.Column("signal_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_hash", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("strategy_id", sa.String(length=64), nullable=False),
        sa.Column("pair", sa.String(length=20), nullable=False),
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column("volume", sa.Numeric(precision=24, scale=12), nullable=False),
        sa.Column("order_type", sa.String(length=12), nullable=False),
        sa.Column("price", sa.Numeric(precision=24, scale=12), nullable=True),
        sa.Column("order_id", sa.String(length=64), nullable=True),
        sa.Column("raw_symbol", sa.String(length=64), nullable=True),
        sa.Column("observed_price", sa.Numeric(precision=24, scale=12), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mode_snapshot", sa.String(length=16), nullable=False),
        sa.Column("route_version", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("external_correlation_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("paper_intent_id", sa.String(length=36), nullable=True),
        sa.Column("execution_target", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source IN ('tradingview', 'mcp')", name="ck_signal_events_source"),
        sa.CheckConstraint("mode_snapshot IN ('bypass_ai', 'advisory')", name="ck_signal_events_mode"),
        sa.CheckConstraint("execution_target = 'kraken_paper'", name="ck_signal_events_target"),
        sa.ForeignKeyConstraint(["route_id"], ["signal_routes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("route_id", "source", "signal_id", name="uq_signal_events_route_source_id"),
    )
    op.create_index("ix_signal_events_route_id", "signal_events", ["route_id"])

    op.create_table(
        "signal_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("route_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_owner", sa.String(length=64), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('ready', 'leased', 'retry_wait', 'complete', 'dead')",
            name="ck_signal_jobs_status",
        ),
        sa.ForeignKeyConstraint(["event_id"], ["signal_events.id"]),
        sa.ForeignKeyConstraint(["route_id"], ["signal_routes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_signal_jobs_event"),
    )
    op.create_index("ix_signal_jobs_route_id", "signal_jobs", ["route_id"])

    op.create_table(
        "signal_evaluations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("candidate_hash", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('approve', 'reject', 'abstain', 'timeout', 'error')",
            name="ck_signal_evaluations_decision",
        ),
        sa.ForeignKeyConstraint(["event_id"], ["signal_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_signal_evaluations_event"),
    )

    op.create_table(
        "signal_audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor_kind", sa.String(length=32), nullable=False),
        sa.Column("actor_subject", sa.String(length=128), nullable=True),
        sa.Column("route_id", sa.String(length=36), nullable=True),
        sa.Column("event_id", sa.String(length=36), nullable=True),
        sa.Column("request_id", sa.String(length=36), nullable=True),
        sa.Column("transition", sa.String(length=64), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("route_version", sa.Integer(), nullable=True),
        sa.Column("policy_version", sa.String(length=32), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signal_audit_events_route_id", "signal_audit_events", ["route_id"])
    op.create_index("ix_signal_audit_events_event_id", "signal_audit_events", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_signal_audit_events_event_id", table_name="signal_audit_events")
    op.drop_index("ix_signal_audit_events_route_id", table_name="signal_audit_events")
    op.drop_table("signal_audit_events")
    op.drop_table("signal_evaluations")
    op.drop_index("ix_signal_jobs_route_id", table_name="signal_jobs")
    op.drop_table("signal_jobs")
    op.drop_index("ix_signal_events_route_id", table_name="signal_events")
    op.drop_table("signal_events")
    op.drop_index("ix_signal_route_credentials_route_id", table_name="signal_route_credentials")
    op.drop_table("signal_route_credentials")
    op.drop_index("ix_signal_routes_owner_user_uid", table_name="signal_routes")
    op.drop_table("signal_routes")
    op.drop_index("uq_paper_order_intents_signal_source_ref", table_name="paper_order_intents")
    op.drop_constraint("ck_paper_order_intents_source", "paper_order_intents", type_="check")
    op.drop_column("paper_order_intents", "source_ref")
    op.drop_column("paper_order_intents", "source")
