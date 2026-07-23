"""Transactions, dedupe, leases, optimistic route updates."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    SignalAuditEvent,
    SignalEvaluation,
    SignalEvent,
    SignalJob,
    SignalRoute,
    SignalRouteCredential,
)


class SignalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_routes(self, owner_uid: str) -> list[SignalRoute]:
        result = await self.session.scalars(
            select(SignalRoute).where(SignalRoute.owner_user_uid == owner_uid).order_by(SignalRoute.created_at.desc())
        )
        return list(result)

    async def get_route(self, route_id: str) -> SignalRoute | None:
        return await self.session.get(SignalRoute, route_id)

    async def get_route_by_public_key(self, public_route_key: str) -> SignalRoute | None:
        return await self.session.scalar(
            select(SignalRoute).where(SignalRoute.public_route_key == public_route_key)
        )

    async def create_route(self, route: SignalRoute) -> SignalRoute:
        self.session.add(route)
        await self.session.flush()
        return route

    async def optimistic_update_route(
        self,
        route: SignalRoute,
        *,
        expected_version: int,
        **fields,
    ) -> SignalRoute | None:
        if route.version != expected_version:
            return None
        for key, value in fields.items():
            if value is not None:
                setattr(route, key, value)
        route.version = expected_version + 1
        route.updated_at = datetime.now(UTC)
        await self.session.flush()
        return route


    async def get_active_credential_by_digest(self, route_id: str, kind: str, digest: str) -> SignalRouteCredential | None:
        return await self.session.scalar(
            select(SignalRouteCredential).where(
                SignalRouteCredential.route_id == route_id,
                SignalRouteCredential.kind == kind,
                SignalRouteCredential.digest == digest,
                SignalRouteCredential.revoked_at.is_(None),
            )
        )

    async def get_active_mcp_credential_by_digest(self, digest: str) -> SignalRouteCredential | None:
        return await self.session.scalar(
            select(SignalRouteCredential).where(
                SignalRouteCredential.kind == "mcp_bearer",
                SignalRouteCredential.digest == digest,
                SignalRouteCredential.revoked_at.is_(None),
            )
        )

    async def active_credentials(self, route_id: str, kind: str) -> list[SignalRouteCredential]:
        result = await self.session.scalars(
            select(SignalRouteCredential).where(
                SignalRouteCredential.route_id == route_id,
                SignalRouteCredential.kind == kind,
                SignalRouteCredential.revoked_at.is_(None),
            )
        )
        return list(result)

    async def add_credential(self, credential: SignalRouteCredential) -> SignalRouteCredential:
        self.session.add(credential)
        await self.session.flush()
        return credential

    async def get_credential(self, credential_id: str) -> SignalRouteCredential | None:
        return await self.session.get(SignalRouteCredential, credential_id)

    async def find_event(self, route_id: str, source: str, signal_id: str) -> SignalEvent | None:
        return await self.session.scalar(
            select(SignalEvent).where(
                SignalEvent.route_id == route_id,
                SignalEvent.source == source,
                SignalEvent.signal_id == signal_id,
            )
        )

    async def insert_event_job_audit(
        self,
        *,
        event: SignalEvent,
        job: SignalJob,
        audit: SignalAuditEvent,
    ) -> None:
        self.session.add(event)
        self.session.add(job)
        self.session.add(audit)
        await self.session.commit()

    async def add_audit(self, audit: SignalAuditEvent) -> None:
        self.session.add(audit)
        await self.session.flush()

    async def transition_event(
        self,
        event: SignalEvent,
        *,
        status: str,
        reason_code: str | None = None,
        paper_intent_id: str | None = None,
    ) -> None:
        event.status = status
        event.reason_code = reason_code
        if paper_intent_id is not None:
            event.paper_intent_id = paper_intent_id
        event.updated_at = datetime.now(UTC)
        await self.session.flush()

    async def claim_job(self, *, worker_id: str, lease_seconds: int) -> SignalJob | None:
        now = datetime.now(UTC)
        stmt = (
            select(SignalJob)
            .where(
                or_(
                    and_(SignalJob.status == "ready", SignalJob.available_at <= now),
                    and_(SignalJob.status == "retry_wait", SignalJob.available_at <= now),
                    and_(
                        SignalJob.status == "leased",
                        SignalJob.lease_expires_at.is_not(None),
                        SignalJob.lease_expires_at < now,
                    ),
                )
            )
            .order_by(SignalJob.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = await self.session.scalar(stmt)
        if job is None:
            return None
        job.status = "leased"
        job.lease_owner = worker_id
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        job.attempts += 1
        job.updated_at = now
        await self.session.commit()
        return job

    async def heartbeat_job(self, job: SignalJob, *, lease_seconds: int) -> None:
        job.lease_expires_at = datetime.now(UTC) + timedelta(seconds=lease_seconds)
        job.updated_at = datetime.now(UTC)
        await self.session.commit()

    async def complete_job(self, job: SignalJob) -> None:
        job.status = "complete"
        job.lease_owner = None
        job.lease_expires_at = None
        job.updated_at = datetime.now(UTC)
        await self.session.commit()

    async def retry_job(self, job: SignalJob, *, delay_seconds: int, error_code: str) -> None:
        job.status = "retry_wait"
        job.last_error_code = error_code
        job.lease_owner = None
        job.lease_expires_at = None
        job.available_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
        job.updated_at = datetime.now(UTC)
        await self.session.commit()

    async def dead_job(self, job: SignalJob, *, error_code: str) -> None:
        job.status = "dead"
        job.last_error_code = error_code
        job.lease_owner = None
        job.lease_expires_at = None
        job.updated_at = datetime.now(UTC)
        await self.session.commit()

    async def get_event(self, event_id: str) -> SignalEvent | None:
        return await self.session.get(SignalEvent, event_id)

    async def add_evaluation(self, evaluation: SignalEvaluation) -> None:
        self.session.add(evaluation)
        await self.session.flush()

    async def queue_depth(self) -> int:
        value = await self.session.scalar(
            select(func.count()).select_from(SignalJob).where(SignalJob.status.in_(("ready", "retry_wait", "leased")))
        )
        return int(value or 0)

    async def oldest_ready_age_seconds(self) -> float | None:
        oldest = await self.session.scalar(
            select(func.min(SignalJob.available_at)).where(SignalJob.status.in_(("ready", "retry_wait")))
        )
        if oldest is None:
            return None
        return max(0.0, (datetime.now(UTC) - oldest).total_seconds())

    async def list_events(
        self,
        *,
        owner_uid: str,
        route_id: str | None,
        source: str | None,
        status: str | None,
        limit: int,
        cursor: str | None,
    ) -> list[SignalEvent]:
        owner_routes = select(SignalRoute.id).where(SignalRoute.owner_user_uid == owner_uid)
        stmt = select(SignalEvent).where(SignalEvent.route_id.in_(owner_routes)).order_by(SignalEvent.created_at.desc())
        if route_id:
            stmt = stmt.where(SignalEvent.route_id == route_id)
        if source:
            stmt = stmt.where(SignalEvent.source == source)
        if status:
            stmt = stmt.where(SignalEvent.status == status)
        if cursor:
            stmt = stmt.where(SignalEvent.created_at < datetime.fromisoformat(cursor))
        stmt = stmt.limit(min(max(limit, 1), 100))
        return list(await self.session.scalars(stmt))

    async def get_evaluation(self, event_id: str) -> SignalEvaluation | None:
        return await self.session.scalar(select(SignalEvaluation).where(SignalEvaluation.event_id == event_id))

    async def count_recent_events(self, route_id: str, *, window_seconds: int = 60) -> int:
        since = datetime.now(UTC) - timedelta(seconds=window_seconds)
        value = await self.session.scalar(
            select(func.count()).select_from(SignalEvent).where(
                SignalEvent.route_id == route_id,
                SignalEvent.created_at >= since,
            )
        )
        return int(value or 0)

    async def backlog_for_route(self, route_id: str) -> int:
        value = await self.session.scalar(
            select(func.count()).select_from(SignalJob).where(
                SignalJob.route_id == route_id,
                SignalJob.status.in_(("ready", "retry_wait", "leased")),
            )
        )
        return int(value or 0)


def new_audit(
    *,
    actor_kind: str,
    actor_subject: str | None,
    route_id: str | None,
    event_id: str | None,
    request_id: str | None,
    transition: str,
    reason_code: str | None = None,
    route_version: int | None = None,
    policy_version: str | None = None,
    details: dict | None = None,
) -> SignalAuditEvent:
    return SignalAuditEvent(
        id=str(uuid4()),
        actor_kind=actor_kind,
        actor_subject=actor_subject,
        route_id=route_id,
        event_id=event_id,
        request_id=request_id,
        transition=transition,
        reason_code=reason_code,
        route_version=route_version,
        policy_version=policy_version,
        details=details,
    )


def new_route(
    *,
    owner_uid: str,
    name: str,
    strategy_id: str,
    pair_allowlist: str,
    max_volume: Decimal,
    max_notional: Decimal | None,
    allowed_order_types: str,
    max_event_age_seconds: int,
    max_rate_per_minute: int,
    max_backlog: int,
    policy_version: str,
) -> SignalRoute:
    return SignalRoute(
        id=str(uuid4()),
        owner_user_uid=owner_uid,
        public_route_key=secrets_public_key(),
        name=name,
        strategy_id=strategy_id,
        mode="advisory",
        enabled=False,
        execution_target="kraken_paper",
        pair_allowlist=pair_allowlist,
        max_volume=max_volume,
        max_notional=max_notional,
        allowed_order_types=allowed_order_types,
        max_event_age_seconds=max_event_age_seconds,
        max_rate_per_minute=max_rate_per_minute,
        max_backlog=max_backlog,
        policy_version=policy_version,
        version=1,
    )


def secrets_public_key() -> str:
    from secrets import token_urlsafe

    return token_urlsafe(18)
