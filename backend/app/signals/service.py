"""Canonical SignalSubmissionService and route/history use cases."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import SignalEvent, SignalJob, SignalRoute, SignalRouteCredential
from ..settings import Settings
from .auth import make_credential, verify_credential
from .domain import SignalSource
from .policy import build_candidate, check_freshness, parse_occurred_at
from .repository import SignalRepository, new_audit, new_route
from .schemas import (
    CredentialReveal,
    McpSubmitArgs,
    SignalAutomationStatus,
    SignalReceipt,
    SignalRouteCreate,
    SignalRoutePatch,
    SignalRouteView,
    SignalSubmissionView,
    TradingViewWebhookBody,
)


class SignalSubmissionService:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def status(self, session: AsyncSession) -> SignalAutomationStatus:
        repo = SignalRepository(session)
        return SignalAutomationStatus(
            signal_routes_enabled=self.settings.signal_routes_enabled,
            tradingview_ingress_enabled=self.settings.tradingview_ingress_enabled,
            mcp_signal_adapter_enabled=self.settings.mcp_signal_adapter_enabled,
            signal_worker_enabled=self.settings.signal_worker_enabled,
            signal_execution_enabled=self.settings.signal_execution_enabled,
            ai_advisory_enabled=self.settings.ai_advisory_enabled,
            queue_depth=await repo.queue_depth(),
            oldest_ready_age_seconds=await repo.oldest_ready_age_seconds(),
            worker_heartbeat_ok=self.settings.signal_worker_enabled,
            advisory_ready=self.settings.ai_advisory_enabled
            or self.settings.advisory_provider == "fake",
        )

    async def list_routes(self, session: AsyncSession, owner_uid: str) -> list[SignalRouteView]:
        repo = SignalRepository(session)
        routes = await repo.list_routes(owner_uid)
        views: list[SignalRouteView] = []
        for route in routes:
            views.append(await self._route_view(repo, route))
        return views

    async def create_route(
        self, session: AsyncSession, owner_uid: str, payload: SignalRouteCreate
    ) -> SignalRouteView:
        if not self.settings.signal_routes_enabled:
            raise HTTPException(status_code=503, detail={"code": "signal_routes_disabled", "message": "signal routes disabled"})
        repo = SignalRepository(session)
        route = new_route(
            owner_uid=owner_uid,
            name=payload.name,
            strategy_id=payload.strategy_id,
            pair_allowlist=payload.pair_allowlist,
            max_volume=payload.max_volume,
            max_notional=payload.max_notional,
            allowed_order_types=payload.allowed_order_types,
            max_event_age_seconds=payload.max_event_age_seconds,
            max_rate_per_minute=payload.max_rate_per_minute,
            max_backlog=payload.max_backlog,
            policy_version=self.settings.signal_policy_version,
        )
        await repo.create_route(route)
        await repo.add_audit(
            new_audit(
                actor_kind="user",
                actor_subject=owner_uid,
                route_id=route.id,
                event_id=None,
                request_id=None,
                transition="route_created",
                route_version=route.version,
                policy_version=route.policy_version,
            )
        )
        await session.commit()
        return await self._route_view(repo, route)

    async def get_route(self, session: AsyncSession, owner_uid: str, route_id: str) -> SignalRouteView:
        repo = SignalRepository(session)
        route = await self._owned_route(repo, owner_uid, route_id)
        return await self._route_view(repo, route)

    async def patch_route(
        self,
        session: AsyncSession,
        owner_uid: str,
        route_id: str,
        payload: SignalRoutePatch,
        *,
        recent_auth: bool,
    ) -> SignalRouteView:
        repo = SignalRepository(session)
        route = await self._owned_route(repo, owner_uid, route_id)
        if payload.mode == "bypass_ai" and route.mode == "advisory" and not recent_auth:
            raise HTTPException(status_code=401, detail={"code": "recent_auth_required", "message": "re-authenticate for Bypass"})
        if payload.enabled is True:
            if not self.settings.signal_routes_enabled:
                raise HTTPException(status_code=503, detail={"code": "signal_routes_disabled", "message": "global gate off"})
            if route.mode == "advisory" and payload.mode != "bypass_ai":
                if not (self.settings.ai_advisory_enabled or self.settings.advisory_provider == "fake"):
                    raise HTTPException(status_code=503, detail={"code": "advisory_unavailable", "message": "AI advisory unavailable"})
        updated = await repo.optimistic_update_route(
            route,
            expected_version=payload.expected_version,
            name=payload.name,
            mode=payload.mode,
            enabled=payload.enabled,
            pair_allowlist=payload.pair_allowlist,
            max_volume=payload.max_volume,
            max_notional=payload.max_notional,
            allowed_order_types=payload.allowed_order_types,
            max_event_age_seconds=payload.max_event_age_seconds,
            max_rate_per_minute=payload.max_rate_per_minute,
            max_backlog=payload.max_backlog,
        )
        if updated is None:
            raise HTTPException(
                status_code=409,
                detail={"code": "route_version_conflict", "message": "route was updated elsewhere"},
            )
        await repo.add_audit(
            new_audit(
                actor_kind="user",
                actor_subject=owner_uid,
                route_id=route.id,
                event_id=None,
                request_id=None,
                transition="route_patched",
                route_version=route.version,
                policy_version=route.policy_version,
                details={"enabled": route.enabled, "mode": route.mode},
            )
        )
        await session.commit()
        return await self._route_view(repo, route)

    async def rotate_credential(
        self,
        session: AsyncSession,
        owner_uid: str,
        route_id: str,
        kind: str,
    ) -> CredentialReveal:
        repo = SignalRepository(session)
        route = await self._owned_route(repo, owner_uid, route_id)
        for existing in await repo.active_credentials(route.id, kind):
            existing.revoked_at = datetime.now(UTC)
        generated = make_credential(kind, self.settings)
        credential = SignalRouteCredential(
            id=str(uuid4()),
            route_id=route.id,
            kind=kind,
            digest=generated.digest,
            pepper_version=generated.pepper_version,
            display_prefix=generated.display_prefix,
        )
        await repo.add_credential(credential)
        await repo.add_audit(
            new_audit(
                actor_kind="user",
                actor_subject=owner_uid,
                route_id=route.id,
                event_id=None,
                request_id=None,
                transition="credential_rotated",
                reason_code=kind,
                route_version=route.version,
            )
        )
        await session.commit()
        return CredentialReveal(
            credential_id=credential.id,
            kind=kind,  # type: ignore[arg-type]
            plaintext=generated.plaintext,
            display_prefix=generated.display_prefix,
            activated_at=credential.activated_at.isoformat(),
        )

    async def revoke_credential(
        self, session: AsyncSession, owner_uid: str, route_id: str, credential_id: str
    ) -> dict[str, str]:
        repo = SignalRepository(session)
        route = await self._owned_route(repo, owner_uid, route_id)
        credential = await repo.get_credential(credential_id)
        if credential is None or credential.route_id != route.id:
            raise HTTPException(status_code=404, detail={"code": "not_found", "message": "resource not found"})
        credential.revoked_at = datetime.now(UTC)
        await repo.add_audit(
            new_audit(
                actor_kind="user",
                actor_subject=owner_uid,
                route_id=route.id,
                event_id=None,
                request_id=None,
                transition="credential_revoked",
                reason_code=credential.kind,
                route_version=route.version,
            )
        )
        await session.commit()
        return {"status": "revoked", "credential_id": credential_id}

    async def list_submissions(
        self,
        session: AsyncSession,
        owner_uid: str,
        *,
        route_id: str | None,
        source: str | None,
        status: str | None,
        cursor: str | None,
        limit: int,
    ) -> list[SignalSubmissionView]:
        repo = SignalRepository(session)
        events = await repo.list_events(
            owner_uid=owner_uid,
            route_id=route_id,
            source=source,
            status=status,
            limit=limit,
            cursor=cursor,
        )
        views: list[SignalSubmissionView] = []
        for event in events:
            evaluation = await repo.get_evaluation(event.id)
            views.append(
                SignalSubmissionView(
                    id=event.id,
                    route_id=event.route_id,
                    source=event.source,  # type: ignore[arg-type]
                    signal_id=event.signal_id,
                    pair=event.pair,
                    side=event.side,
                    volume=str(event.volume),
                    order_type=event.order_type,
                    mode_snapshot=event.mode_snapshot,
                    status=event.status,
                    reason_code=event.reason_code,
                    request_id=event.request_id,
                    paper_intent_id=event.paper_intent_id,
                    occurred_at=event.occurred_at.isoformat(),
                    created_at=event.created_at.isoformat(),
                    updated_at=event.updated_at.isoformat(),
                    advisory_decision=evaluation.decision if evaluation else None,
                )
            )
        return views

    async def get_submission(
        self, session: AsyncSession, owner_uid: str, submission_id: str
    ) -> SignalSubmissionView:
        repo = SignalRepository(session)
        event = await repo.get_event(submission_id)
        if event is None:
            raise HTTPException(status_code=404, detail={"code": "not_found", "message": "resource not found"})
        route = await repo.get_route(event.route_id)
        if route is None or route.owner_user_uid != owner_uid:
            raise HTTPException(status_code=404, detail={"code": "not_found", "message": "resource not found"})
        evaluation = await repo.get_evaluation(event.id)
        return SignalSubmissionView(
            id=event.id,
            route_id=event.route_id,
            source=event.source,  # type: ignore[arg-type]
            signal_id=event.signal_id,
            pair=event.pair,
            side=event.side,
            volume=str(event.volume),
            order_type=event.order_type,
            mode_snapshot=event.mode_snapshot,
            status=event.status,
            reason_code=event.reason_code,
            request_id=event.request_id,
            paper_intent_id=event.paper_intent_id,
            occurred_at=event.occurred_at.isoformat(),
            created_at=event.created_at.isoformat(),
            updated_at=event.updated_at.isoformat(),
            advisory_decision=evaluation.decision if evaluation else None,
        )

    async def submit_tradingview(
        self,
        session: AsyncSession,
        *,
        public_route_key: str,
        body: TradingViewWebhookBody,
        request_id: str,
        external_correlation_id: str | None,
    ) -> SignalReceipt:
        if not (self.settings.signal_routes_enabled and self.settings.tradingview_ingress_enabled):
            raise HTTPException(status_code=503, detail={"code": "ingress_disabled", "message": "ingress disabled"})
        repo = SignalRepository(session)
        route = await repo.get_route_by_public_key(public_route_key)
        if route is None:
            raise HTTPException(status_code=401, detail={"code": "auth_failed", "message": "authentication failed"})
        credential = await self._verify_route_credential(repo, route, "tradingview_secret", body.credential)
        return await self._accept(
            repo,
            route=route,
            credential=credential,
            source="tradingview",
            signal_id=body.signal_id,
            schema_version=body.schema_version,
            occurred_at_raw=body.occurred_at,
            strategy_id=body.strategy_id,
            pair=body.pair,
            side=body.side,
            volume=body.volume,
            order_type=body.order_type,
            price=body.price,
            order_id=body.order_id,
            raw_symbol=body.raw_symbol,
            observed_price=body.observed_price,
            pattern_bias=body.pattern_bias,
            pattern_confidence=body.pattern_confidence,
            request_id=request_id,
            external_correlation_id=external_correlation_id,
        )

    async def submit_mcp(
        self,
        session: AsyncSession,
        *,
        bearer: str,
        args: McpSubmitArgs,
        request_id: str,
    ) -> SignalReceipt:
        if not (self.settings.signal_routes_enabled and self.settings.mcp_signal_adapter_enabled):
            raise HTTPException(status_code=503, detail={"code": "ingress_disabled", "message": "ingress disabled"})
        repo = SignalRepository(session)
        # Bind route from credential — never accept route_id from tool args.
        credential, route = await self._resolve_mcp_bearer(repo, bearer)
        volume = args.volume_decimal()
        price = args.price_decimal()
        observed = None
        if args.observed_price is not None:
            from decimal import Decimal as D

            observed = D(args.observed_price)
        return await self._accept(
            repo,
            route=route,
            credential=credential,
            source="mcp",
            signal_id=args.idempotency_key,
            schema_version=1,
            occurred_at_raw=args.occurred_at,
            strategy_id=args.strategy_id,
            pair=args.pair,
            side=args.side,
            volume=volume,
            order_type=args.order_type,
            price=price,
            order_id=None,
            raw_symbol=None,
            observed_price=observed,
            pattern_bias=args.pattern_bias,
            pattern_confidence=args.pattern_confidence_decimal(),
            request_id=request_id,
            external_correlation_id=None,
        )

    async def submit_fable_engine(
        self,
        session: AsyncSession,
        *,
        strategy_id: str,
        signal_id: str,
        occurred_at: str,
        pair: str,
        side: str,
        volume: Decimal,
        observed_price: Decimal | None,
        request_id: str,
    ) -> SignalReceipt:
        """In-process intake for FableEngine — no credential; route bound by strategy_id."""
        if not (self.settings.signal_routes_enabled and self.settings.fable_engine_enabled):
            raise HTTPException(
                status_code=503,
                detail={"code": "ingress_disabled", "message": "fable engine intake disabled"},
            )
        repo = SignalRepository(session)
        route = await repo.find_enabled_route_by_strategy(strategy_id)
        if route is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "no_route_for_strategy",
                    "message": f"no enabled route with strategy_id={strategy_id}",
                },
            )
        from .rna_context import get_rna_context

        pattern_bias: str | None = None
        pattern_confidence: Decimal | None = None
        ctx = get_rna_context()
        if ctx is not None:
            norm_pair = pair.strip().upper().replace("/", "").replace("-", "")
            sym = (ctx.symbol or "").replace("/", "").replace("-", "").upper()
            if not sym or norm_pair.startswith(sym) or sym in norm_pair:
                pattern_bias = ctx.bias
                pattern_confidence = ctx.confidence
        return await self._accept(
            repo,
            route=route,
            credential=None,
            source="fable_engine",
            signal_id=signal_id,
            schema_version=1,
            occurred_at_raw=occurred_at,
            strategy_id=strategy_id,
            pair=pair,
            side=side,
            volume=volume,
            order_type="market",
            price=None,
            order_id=None,
            raw_symbol=None,
            observed_price=observed_price,
            request_id=request_id,
            external_correlation_id=None,
            pattern_bias=pattern_bias,
            pattern_confidence=pattern_confidence,
        )

    async def _accept(
        self,
        repo: SignalRepository,
        *,
        route: SignalRoute,
        credential: SignalRouteCredential | None,
        source: SignalSource,
        signal_id: str,
        schema_version: int,
        occurred_at_raw: str,
        strategy_id: str,
        pair: str,
        side: str,
        volume: Decimal,
        order_type: str,
        price: Decimal | None,
        order_id: str | None,
        raw_symbol: str | None,
        observed_price: Decimal | None,
        request_id: str,
        external_correlation_id: str | None,
        pattern_bias: str | None = None,
        pattern_confidence: Decimal | None = None,
    ) -> SignalReceipt:
        try:
            occurred_at = parse_occurred_at(occurred_at_raw)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "invalid_timestamp", "message": str(exc)}) from exc

        candidate = build_candidate(
            schema_version=schema_version,
            signal_id=signal_id,
            occurred_at=occurred_at.isoformat().replace("+00:00", "Z"),
            strategy_id=strategy_id,
            pair=pair,
            side=side,
            volume=volume,
            order_type=order_type,
            price=price,
            order_id=order_id,
            raw_symbol=raw_symbol,
            observed_price=observed_price,
            source=source,
            pattern_bias=pattern_bias,
            pattern_confidence=pattern_confidence,
        )

        existing = await repo.find_event(route.id, source, signal_id)
        if existing is not None:
            if existing.canonical_hash == candidate.canonical_hash:
                return SignalReceipt(
                    submission_id=UUID(existing.id),
                    replayed=True,
                    request_id=existing.request_id,
                )
            raise HTTPException(
                status_code=409,
                detail={"code": "signal_conflict", "message": "signal_id collision with different payload"},
            )

        freshness = check_freshness(occurred_at, self.settings, route)
        if not freshness.ok:
            raise HTTPException(status_code=422, detail={"code": freshness.reason_code, "message": "event rejected"})

        event_id = str(uuid4())
        event = SignalEvent(
            id=event_id,
            route_id=route.id,
            source=source,
            credential_id=credential.id if credential is not None else None,
            signal_id=signal_id,
            canonical_hash=candidate.canonical_hash,
            schema_version=schema_version,
            strategy_id=strategy_id,
            pair=pair,
            side=side,
            volume=str(volume),
            order_type=order_type,
            price=str(price) if price is not None else None,
            order_id=order_id,
            raw_symbol=raw_symbol,
            observed_price=str(observed_price) if observed_price is not None else None,
            occurred_at=occurred_at,
            mode_snapshot=route.mode,
            route_version=route.version,
            policy_version=route.policy_version,
            request_id=request_id,
            external_correlation_id=external_correlation_id,
            status="queued",
            execution_target="kraken_paper",
            metadata_json={
                "order_id": order_id,
                "raw_symbol": raw_symbol,
                **(
                    {"pattern_bias": pattern_bias} if pattern_bias is not None else {}
                ),
                **(
                    {"pattern_confidence": str(pattern_confidence)} if pattern_confidence is not None else {}
                ),
            },
        )
        job = SignalJob(
            id=str(uuid4()),
            event_id=event_id,
            route_id=route.id,
            status="ready",
        )
        audit = new_audit(
            actor_kind="ingress",
            actor_subject=source,
            route_id=route.id,
            event_id=event_id,
            request_id=request_id,
            transition="received_queued",
            route_version=route.version,
            policy_version=route.policy_version,
        )
        if credential is not None:
            credential.last_used_at = datetime.now(UTC)
        await repo.insert_event_job_audit(event=event, job=job, audit=audit)
        return SignalReceipt(submission_id=UUID(event_id), replayed=False, request_id=request_id)

    async def _verify_route_credential(
        self,
        repo: SignalRepository,
        route: SignalRoute,
        kind: str,
        plaintext: str,
    ) -> SignalRouteCredential:
        for credential in await repo.active_credentials(route.id, kind):
            if verify_credential(
                plaintext,
                credential.digest,
                self.settings,
                pepper_version=credential.pepper_version,
                revoked_at=credential.revoked_at,
                expires_at=credential.expires_at,
            ):
                return credential
        raise HTTPException(status_code=401, detail={"code": "auth_failed", "message": "authentication failed"})

    async def _resolve_mcp_bearer(
        self, repo: SignalRepository, bearer: str
    ) -> tuple[SignalRouteCredential, SignalRoute]:
        # Scan active MCP credentials; constant-time per credential via hmac.compare_digest.
        from sqlalchemy import select

        from ..models import SignalRouteCredential as Cred

        result = await repo.session.scalars(
            select(Cred).where(Cred.kind == "mcp_bearer", Cred.revoked_at.is_(None))
        )
        for credential in result:
            if verify_credential(
                bearer,
                credential.digest,
                self.settings,
                pepper_version=credential.pepper_version,
                revoked_at=credential.revoked_at,
                expires_at=credential.expires_at,
            ):
                route = await repo.get_route(credential.route_id)
                if route is None:
                    break
                return credential, route
        raise HTTPException(status_code=401, detail={"code": "auth_failed", "message": "authentication failed"})

    async def _owned_route(self, repo: SignalRepository, owner_uid: str, route_id: str) -> SignalRoute:
        route = await repo.get_route(route_id)
        if route is None or route.owner_user_uid != owner_uid:
            raise HTTPException(status_code=404, detail={"code": "not_found", "message": "resource not found"})
        return route

    async def _route_view(self, repo: SignalRepository, route: SignalRoute) -> SignalRouteView:
        tv = await repo.active_credentials(route.id, "tradingview_secret")
        mcp = await repo.active_credentials(route.id, "mcp_bearer")
        return SignalRouteView(
            id=route.id,
            public_route_key=route.public_route_key,
            name=route.name,
            strategy_id=route.strategy_id,
            mode=route.mode,  # type: ignore[arg-type]
            enabled=route.enabled,
            execution_target="kraken_paper",
            pair_allowlist=route.pair_allowlist,
            max_volume=str(route.max_volume),
            max_notional=str(route.max_notional) if route.max_notional is not None else None,
            allowed_order_types=route.allowed_order_types,
            max_event_age_seconds=route.max_event_age_seconds,
            max_rate_per_minute=route.max_rate_per_minute,
            max_backlog=route.max_backlog,
            policy_version=route.policy_version,
            version=route.version,
            created_at=route.created_at.isoformat(),
            updated_at=route.updated_at.isoformat(),
            webhook_url_path=f"/api/v1/webhooks/tradingview/{route.public_route_key}",
            has_tradingview_credential=bool(tv),
            has_mcp_credential=bool(mcp),
        )
