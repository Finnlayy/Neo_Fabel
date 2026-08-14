"""Provider-neutral typed SignalEvaluator protocol and deterministic fake."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..settings import Settings
from .domain import AdvisoryDecision, CanonicalSignalCandidate


@dataclass(frozen=True)
class EvaluationResult:
    decision: AdvisoryDecision
    reason_code: str
    candidate_hash: str
    policy_version: str
    provider: str
    model: str
    prompt_version: str
    latency_ms: int


class SignalEvaluator(Protocol):
    async def evaluate(
        self,
        candidate: CanonicalSignalCandidate,
        *,
        policy_version: str,
        deterministic_ok: bool,
    ) -> EvaluationResult: ...


@dataclass
class FakeSignalEvaluator:
    """Deterministic fake for tests and pre-provider-approval environments."""

    settings: Settings
    force_decision: AdvisoryDecision | None = None

    async def evaluate(
        self,
        candidate: CanonicalSignalCandidate,
        *,
        policy_version: str,
        deterministic_ok: bool,
    ) -> EvaluationResult:
        if not deterministic_ok:
            return EvaluationResult(
                decision="abstain",
                reason_code="deterministic_failed",
                candidate_hash=candidate.canonical_hash,
                policy_version=policy_version,
                provider=self.settings.advisory_provider,
                model=self.settings.advisory_model,
                prompt_version=self.settings.advisory_prompt_version,
                latency_ms=0,
            )
        if self.force_decision is not None:
            decision: AdvisoryDecision = self.force_decision
        else:
            # Pattern → Signal-Route Boost (deterministic stub):
            # If RNA provided a pattern bias+confidence, let it steer the advisory decision.
            decision = "approve"
            if candidate.pattern_bias is not None and candidate.pattern_confidence is not None:
                confidence = float(candidate.pattern_confidence)
                threshold = 65.0
                expected = "bullish" if candidate.side == "buy" else "bearish"

                if candidate.pattern_bias == "neutral":
                    decision = "abstain"
                elif candidate.pattern_bias == expected:
                    decision = "approve" if confidence >= threshold else "abstain"
                else:
                    decision = "reject" if confidence >= threshold else "abstain"
        reason = {
            "approve": "canonical_signal_consistent",
            "reject": "canonical_signal_rejected",
            "abstain": "canonical_signal_uncertain",
            "timeout": "advisory_timeout",
            "error": "advisory_provider_error",
        }[decision]
        return EvaluationResult(
            decision=decision,
            reason_code=reason,
            candidate_hash=candidate.canonical_hash,
            policy_version=policy_version,
            provider=self.settings.advisory_provider,
            model=self.settings.advisory_model,
            prompt_version=self.settings.advisory_prompt_version,
            latency_ms=1,
        )


def normalize_evaluation(
    result: EvaluationResult,
    *,
    expected_hash: str,
    expected_policy: str,
    expected_provider: str,
    expected_model: str,
) -> EvaluationResult:
    """Fail closed on hash/policy/model mismatch or non-approve decisions."""
    if result.candidate_hash != expected_hash:
        return EvaluationResult(
            decision="abstain",
            reason_code="candidate_hash_mismatch",
            candidate_hash=expected_hash,
            policy_version=expected_policy,
            provider=expected_provider,
            model=expected_model,
            prompt_version=result.prompt_version,
            latency_ms=result.latency_ms,
        )
    if result.policy_version != expected_policy:
        return EvaluationResult(
            decision="abstain",
            reason_code="policy_version_mismatch",
            candidate_hash=expected_hash,
            policy_version=expected_policy,
            provider=expected_provider,
            model=expected_model,
            prompt_version=result.prompt_version,
            latency_ms=result.latency_ms,
        )
    if result.provider != expected_provider or result.model != expected_model:
        return EvaluationResult(
            decision="abstain",
            reason_code="model_mismatch",
            candidate_hash=expected_hash,
            policy_version=expected_policy,
            provider=expected_provider,
            model=expected_model,
            prompt_version=result.prompt_version,
            latency_ms=result.latency_ms,
        )
    if result.decision not in {"approve", "reject", "abstain", "timeout", "error"}:
        return EvaluationResult(
            decision="abstain",
            reason_code="malformed_decision",
            candidate_hash=expected_hash,
            policy_version=expected_policy,
            provider=expected_provider,
            model=expected_model,
            prompt_version=result.prompt_version,
            latency_ms=result.latency_ms,
        )
    return result
