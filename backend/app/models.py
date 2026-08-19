from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PaperOrderIntent(Base):
    __tablename__ = "paper_order_intents"
    __table_args__ = (
        Index("ix_paper_order_intents_user_idempotency", "user_uid", "idempotency_key", unique=True),
        Index(
            "uq_paper_order_intents_signal_source_ref",
            "source_ref",
            unique=True,
            postgresql_where=text("source = 'signal' AND source_ref IS NOT NULL"),
        ),
        CheckConstraint("source IN ('manual', 'signal')", name="ck_paper_order_intents_source"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_uid: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(36), nullable=False)
    pair: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    volume: Mapped[str] = mapped_column(Numeric(24, 12), nullable=False)
    order_type: Mapped[str] = mapped_column(String(12), nullable=False)
    price: Mapped[str | None] = mapped_column(Numeric(24, 12), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    source_ref: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SignalRoute(Base):
    __tablename__ = "signal_routes"
    __table_args__ = (
        UniqueConstraint("public_route_key", name="uq_signal_routes_public_key"),
        CheckConstraint("mode IN ('bypass_ai', 'advisory')", name="ck_signal_routes_mode"),
        CheckConstraint("execution_target = 'kraken_paper'", name="ck_signal_routes_target"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_user_uid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    public_route_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="advisory")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    execution_target: Mapped[str] = mapped_column(String(32), nullable=False, default="kraken_paper")
    pair_allowlist: Mapped[str] = mapped_column(
        Text, nullable=False, default="ADAUSD,XRPUSD,ADAEUR,XRPEUR"
    )
    max_volume: Mapped[Decimal] = mapped_column(Numeric(24, 12), nullable=False, default=Decimal("0.01"))
    max_notional: Mapped[Decimal | None] = mapped_column(Numeric(24, 12), nullable=True)
    allowed_order_types: Mapped[str] = mapped_column(String(64), nullable=False, default="market,limit")
    max_event_age_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    max_rate_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    max_backlog: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    max_open_exposure: Mapped[Decimal | None] = mapped_column(Numeric(24, 12), nullable=True)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    credentials: Mapped[list["SignalRouteCredential"]] = relationship(back_populates="route")


class SignalRouteCredential(Base):
    __tablename__ = "signal_route_credentials"
    __table_args__ = (
        CheckConstraint("kind IN ('tradingview_secret', 'mcp_bearer')", name="ck_signal_credentials_kind"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    route_id: Mapped[str] = mapped_column(String(36), ForeignKey("signal_routes.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    digest: Mapped[str] = mapped_column(String(128), nullable=False)
    pepper_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    display_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    route: Mapped[SignalRoute] = relationship(back_populates="credentials")


class SignalEvent(Base):
    __tablename__ = "signal_events"
    __table_args__ = (
        UniqueConstraint("route_id", "source", "signal_id", name="uq_signal_events_route_source_id"),
        CheckConstraint(
            "source IN ('tradingview', 'mcp', 'fable_engine')",
            name="ck_signal_events_source",
        ),
        CheckConstraint(
            "mode_snapshot IN ('bypass_ai', 'advisory')",
            name="ck_signal_events_mode",
        ),
        CheckConstraint("execution_target = 'kraken_paper'", name="ck_signal_events_target"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    route_id: Mapped[str] = mapped_column(String(36), ForeignKey("signal_routes.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    credential_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    signal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    canonical_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    pair: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    volume: Mapped[str] = mapped_column(Numeric(24, 12), nullable=False)
    order_type: Mapped[str] = mapped_column(String(12), nullable=False)
    price: Mapped[str | None] = mapped_column(Numeric(24, 12), nullable=True)
    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_symbol: Mapped[str | None] = mapped_column(String(64), nullable=True)
    observed_price: Mapped[str | None] = mapped_column(Numeric(24, 12), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    mode_snapshot: Mapped[str] = mapped_column(String(16), nullable=False)
    route_version: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    external_correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="received")
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    paper_intent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    execution_target: Mapped[str] = mapped_column(String(32), nullable=False, default="kraken_paper")
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


class SignalJob(Base):
    __tablename__ = "signal_jobs"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_signal_jobs_event"),
        CheckConstraint(
            "status IN ('ready', 'leased', 'retry_wait', 'complete', 'dead')",
            name="ck_signal_jobs_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("signal_events.id"), nullable=False)
    route_id: Mapped[str] = mapped_column(String(36), ForeignKey("signal_routes.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ready")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


class SignalEvaluation(Base):
    __tablename__ = "signal_evaluations"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_signal_evaluations_event"),
        CheckConstraint(
            "decision IN ('approve', 'reject', 'abstain', 'timeout', 'error')",
            name="ck_signal_evaluations_decision",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("signal_events.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


class SignalAuditEvent(Base):
    __tablename__ = "signal_audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_subject: Mapped[str | None] = mapped_column(String(128), nullable=True)
    route_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    event_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    transition: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    route_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


class OrchestratorDecisionLog(Base):
    """User-scoped audit record for advisory-only orchestrator output."""

    __tablename__ = "orchestrator_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision_type IN ('market_regime', 'signal_quality', 'full_decision')",
            name="ck_orchestrator_decisions_type",
        ),
        CheckConstraint(
            "status IN ('success', 'error')",
            name="ck_orchestrator_decisions_status",
        ),
        Index(
            "ix_orchestrator_decisions_user_created",
            "user_uid",
            "created_at",
        ),
        Index(
            "ix_orchestrator_decisions_user_type_created",
            "user_uid",
            "decision_type",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_uid: Mapped[str] = mapped_column(String(128), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    decision_type: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    input_summary: Mapped[dict] = mapped_column(JSON, nullable=False)
    output_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
