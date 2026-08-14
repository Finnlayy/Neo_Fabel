# Bundled strategies

| Id | File | Role |
|----|------|------|
| `ltm_willy_v130` | `liquidity_trail_matrix_v1_3_0.pine` | **Liquidity Trail Matrix** (Finn Powers / WillyAlgoTrader v1.3) — precision ATR-trail + scored retest analyzer. Neo runs a Python port in `backend/app/integrations/backtest/ltm_analyzer.py` for optimizer metrics; keep this Pine file in sync with TradingView for tvremix/export. |
| `btc_luxalgo_confluence_15m_v1` | `BTCUSDT_P_15m_LuxAlgo_Confluence_Strategy_v1.pine` | BTCUSDT.P 15m LuxAlgo confluence strategy — maps external LuxAlgo Signals & Overlays plots into entries. |
| `btc_pf2_duration_15m_v1` | `BTCUSDT_P_15m_PF2_Duration_Strategy_v1.pine` | BTCUSDT.P 15m PF>2 duration strategy — targets ~1–3h average trade length. |
| `clean_trade_quantum_v8` | `CleanTradeQuantum_Refactored_v8_fixed.pine` | CleanTradeQuantum v8 — 5m SMC order-block / premium-discount quantum strategy. |
| `competition_hype_1m_pionex` | `CompetitionBot_HYPEUSDT_1m_output1_pionex.pine` | CompetitionBot HYPEUSDT 1m — direct Pionex Signal Bot webhook alerts. |
| `eth_glintnews_pionex_v6` | `ETH_USDT_GlintNews_PionexBot_v6_strategy.pine` | ETH/USDT Glint News Pionex bot v6 strategy template. |
| `luxalgo_connector_bridge_v1` | `LuxAlgo_Connector_Strategy_Bridge_v1.pine` | LuxAlgo connector bridge — external Lux signals in, strategy.entry/close out. |
| `mem_mtf_cisd_montecarlo_v6` | `Mem_MTF_CISD_MonteCarlo_Pionex_v6.pine` | MTF CISD + OB/FVG with Monte Carlo gate and Pionex order alerts. |
| `mtf_cisd_ob_fvg_wti5m_live` | `MTF_CISD_OB_FVG_v2_WTI5M_STRATEGY_LIVE.pine` | MTF CISD + OB/FVG hybrid — WTI/USDT.P 5m live / NY-session defaults. |
| `onnx_qm_hub_v2_strategy` | `ONNX_QM_Hub_v2_strategy.pine` | ONNX Quant Management Hub v2 as a TradingView strategy (trades + scan alerts). |
| `onnx_qm_hub_v2` | `ONNX_Quant_Management_Hub_v2.pine` | ONNX Quant Management Hub v2 indicator — scan/alert overlay (no strategy trades). |
| `pin_bar_magic_v1` | `Pin_Bar_Magic_v1_fixed.pine` | Pin Bar Magic v1 — H1 pin-bar entries with ATR stop / trail. |
| `quantum_forex_pionex_direct_v2` | `QuantumForexTrader_v2_reconstructed_pionex_direct.pine` | QuantumForexTrader v2 reconstructed — direct Pionex Signal Bot alerts. |
| `recovery_center_alpha_mos_v6` | `Recovery_Center_Alpha_MOS_BTCUSDT_P_5m_optimized_v6.pine` | Recovery Center Alpha + MOS — BTCUSDT.P 5m optimized v6. |
| `recovery_center_alpha_v1` | `Recovery_Center_Alpha_working_v1.pine` | Recovery Center Alpha working v1 — fractal risk-managed entries. |
| `wti_quantdesk_pro_v4_1` | `WTI_USDT_QuantDesk_Pro_v4_1_fixed.pine` | WTI/USDT.P QuantDesk Pro v4.1 — 1m oil scalping (Margex-style cash qty). |
| `bprc_pro_institutional_v3` | `BPRC_PRO_Institutional_Strategy_clean_v3_alertcalls.pine` | BPRC PRO Institutional clean v3 — strategy-driven `alert()` webhook JSON. |
| `cleanroom_inst_imbalance_pionex` | `Cleanroom_Institutional_Imbalance_Pionex.pine` | Cleanroom Institutional Imbalance Framework (CIIF) — FVG/CVMI + HTF order blocks + Pionex alerts. |

Bundled files are full TradingView chart scripts. Re-paste from TV when you change a strategy on-chart. Probe catalog entries live in `backend/app/integrations/tvapi_optimizer.py` → `_probe_strategies()`.
