"""Create durable paper order intents.

Revision ID: 0001_paper_order_intents
"""
import sqlalchemy as sa
from alembic import op

revision = "0001_paper_order_intents"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_order_intents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_uid", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=36), nullable=False),
        sa.Column("pair", sa.String(length=20), nullable=False),
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column("volume", sa.Numeric(precision=24, scale=12), nullable=False),
        sa.Column("order_type", sa.String(length=12), nullable=False),
        sa.Column("price", sa.Numeric(precision=24, scale=12), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_paper_order_intents_user_idempotency", "paper_order_intents", ["user_uid", "idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_paper_order_intents_user_idempotency", table_name="paper_order_intents")
    op.drop_table("paper_order_intents")
