# Changelog

## Unreleased

- Add an authenticated, advisory-only TradeAgent orchestrator with validated
  market-regime, signal-quality, full-decision, and history APIs.
- Connect the Master Orchestrator dashboard through `src/api/orchestrator.ts`.
- Wire the optimizer visualization schemas to real TVAPI sweep results and
  remove synthetic metrics, random Monte-Carlo points, and placeholder health polling.
- Add user-scoped PostgreSQL audit history via Alembic revision
  `0004_orchestrator_decisions`.
- Sanitize `.env.example` and keep all trading and signal execution defaults off.
