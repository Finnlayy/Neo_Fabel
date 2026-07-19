# Chronos Agent — Kronos-inspired K-Line Language Model (Neo Fabel)

Status: **Phase 0 scaffold in progress**  
Codename: **Chronos** (our agent). Architecture inspired by Kronos (AAAI 2026 / open research), **not** a wholesale copy of proprietary weights.

## Non-negotiables

- Paper / research only — never wire Chronos logits into live Kraken or Signal Routes dispatch.
- Blindfolded / context-free: no ticker IDs, no absolute prices in model features; causal Z-score only.
- Population σ (`ddof=0`), clip ±5, float32 — bit-reproducible path toward ONNX/native.
- Coarse→Fine factorization (10+10 bit) before any autoregressive decoder.
- Live trading remains gated by existing autonomy settings.

## Mapping Kronos → Neo Fabel Chronos

| Kronos concept | Chronos module | Phase |
|----------------|----------------|-------|
| Causal Z-Score OHLCVA | `backend/app/chronos/normalize.py` | 1 |
| BSQ + sign shortcut + coarse/fine | `backend/app/chronos/bsq.py` | 1 |
| Tokenizer autoencoder | `backend/app/chronos/tokenizer.py` | 2 |
| Causal decoder (mini) | `backend/app/chronos/decoder.py` | 3 |
| ONNX export / INT8 | `backend/app/integrations/onnx/` + Chronos export | 4 |
| Agent + Academy + UI | `agent_defs`, Academy drills, SubAgents | 1–5 |
| Monte-Carlo / bands | `backend/app/chronos/predictor.py` + `plot_prediction.py` | 1 |
| matplotlib charts (OHLC / Z / tokens) | `backend/app/chronos/charts.py` + `POST /charts` | 1 |
| Kronos-style GT/Pred plots | `POST /api/v1/chronos/predict` (blue GT / red Pred + MC band) | 1 |

Reuse existing: OHLCV fetch (`ccxt_market`, `tvapi_optimizer`), ONNX router, Academy, `blind_patterns` (rules channel stays separate).

## Phases

### Phase 1 — Language substrate (now)
1. Causal window normalizer `(L, 6)` OHLCVA → clipped Z-scores + μ/σ metadata for denorm.
2. BSQ encode/decode: 20-D → 20 bits → `s1,s2 ∈ [0,1023]`; entropy helper for training later.
3. HTTP: `POST /api/v1/chronos/normalize`, `POST /api/v1/chronos/tokenize` (stub encoder → random/projection until AE trained).
4. Agent id `chronos` in Academy + UI roster (advisory only).

### Phase 2 — Tokenizer AE
- Small Transformer AE → latent 20-D → BSQ.
- Losses: L_coarse + L_fine + λ L_quant (+ entropy).
- Checkpoint under `backend/data/chronos/`.

### Phase 3 — Chronos-mini decoder
- Causal decoder, coarse-then-fine prediction.
- Context target: up to 512 bars first; 2048 as stretch (Chronos-mini profile).
- Eval: RankIC / MAE on held-out paper windows — no live money.

### Phase 4 — ONNX hot path
- Export tokenizer+decoder subgraphs; ORT CPU; optional dynamic INT8.
- `POST /api/v1/chronos/infer` with latency metrics (p50/p99).

### Phase 5 — Product wiring
- SubAgent `chronos` thoughts = blind geometry summary + Chronos distribution summary.
- Academy drills: `kline_language` via `chronos_drills.py` — tokenize + predict self-play in training cycles.
- Optional Qdrant: store pattern-token fingerprints (not absolute prices).
- **Never** auto-call `/api/v1/trade/execute` from Chronos.

## Explicitly deferred
- 12.1B pretrain / 45 exchanges (use public OHLCV + synthetic + our market APIs).
- Spherical Leech Quantization.
- RLHF / LLM-as-judge loop.
- MQL5 native port.

## Success criteria (Phase 1)
- [ ] Same OHLCVA window → deterministic Z-scores (population σ, clip ±5).
- [ ] Same latent z → deterministic `(s1, s2)` via BSQ.
- [ ] API round-trip works with `AUTH_DEV_BYPASS` / Firebase.
- [ ] Agent `chronos` visible; no path to live order placement.
