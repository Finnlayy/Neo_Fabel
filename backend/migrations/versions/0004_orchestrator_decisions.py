"""Add user-scoped advisory orchestrator decision audit.

Revision ID: 0004_orchestrator_decisions
Revises: 0003_fable_engine_source
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_orchestrator_decisions"
down_revision = "0003_fable_engine_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orchestrator_decisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_uid", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("decision_type", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("input_summary", sa.JSON(), nullable=False),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision_type IN ('market_regime', 'signal_quality', 'full_decision')",
            name="ck_orchestrator_decisions_type",
        ),
        sa.CheckConstraint(
            "status IN ('success', 'error')",
            name="ck_orchestrator_decisions_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index(
        "ix_orchestrator_decisions_user_created",
        "orchestrator_decisions",
        ["user_uid", "created_at"],
    )
    op.create_index(
        "ix_orchestrator_decisions_user_type_created",
        "orchestrator_decisions",
        ["user_uid", "decision_type", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_orchestrator_decisions_user_type_created",
        table_name="orchestrator_decisions",
    )
    op.drop_index(
        "ix_orchestrator_decisions_user_created",
        table_name="orchestrator_decisions",
    )
    op.drop_table("orchestrator_decisions")
