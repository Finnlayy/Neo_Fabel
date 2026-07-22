# Genetic Forward Optimization Report

## Scope

- Instrument Universe: `USDT pairs`
- Timeframes: `15m`, `30m`, `1h`
- Objective: `profit max with maximum safety`
- Optimization Type: `Genetic Forward Optimization`

## Configuration

| Parameter | Value |
| --- | --- |
| Generation Size | `30` |
| Number of Generations | `50` |
| Survivors per Generation | `3` |
| Mutation Rate | `5%` |
| Mutation Magnitude | `40%` |
| Cross Threshold | `20%` |
| Selection Rule | `Top 3 only` |
| Safety Bias | `High` |

## Evaluation Model

| Metric | Description | Weight |
| --- | --- | --- |
| Net Profit | Total realized return | `High` |
| Max Drawdown | Peak-to-trough loss | `Very High` |
| Profit Factor | Gross profit / gross loss | `High` |
| Win Rate | Hit ratio | `Medium` |
| Expectancy | Average trade edge | `High` |
| Sharpe / Sortino | Risk-adjusted return | `High` |
| Trade Count | Statistical robustness | `Medium` |
| Recovery Factor | Return vs drawdown | `Very High` |
| Safety Score | Stability, slippage, gap tolerance, loss clustering | `Very High` |

## Parameter Family

| Family | Parameters | Allowed Range |
| --- | --- | --- |
| Trend Filter | `ema_fast`, `ema_slow`, `htf_alignment` | `adaptive` |
| Entry Quality | `min_confidence`, `vol_mult`, `cisd_window` | `tight to moderate` |
| Risk Control | `sl_atr_mul`, `tp_atr_mul`, `max_daily_move_pct` | `conservative` |
| Session Control | `use_session`, `session_time` | `symbol-specific` |
| Exit Logic | `send_close`, `reverse_exit`, `blocker_exit` | `enabled` |

## Top 3 Results

### Rank 1

| Field | Value |
| --- | --- |
| Pair | `<PAIR>` |
| Timeframe | `<TF>` |
| Fitness Score | `<SCORE>` |
| Net Profit | `<NET_PROFIT>` |
| Max Drawdown | `<MAX_DD>` |
| Profit Factor | `<PROFIT_FACTOR>` |
| Win Rate | `<WIN_RATE>` |
| Trades | `<TRADES>` |
| Safety Score | `<SAFETY_SCORE>` |

| Parameter | Value |
| --- | --- |
| `min_conf` | `<VALUE>` |
| `sl_atr_mul` | `<VALUE>` |
| `tp_atr_mul` | `<VALUE>` |
| `vol_mult` | `<VALUE>` |
| `max_daily_move_pct` | `<VALUE>` |
| `use_session` | `<VALUE>` |
| `session_time` | `<VALUE>` |
| `contracts` | `<VALUE>` |

### Rank 2

| Field | Value |
| --- | --- |
| Pair | `<PAIR>` |
| Timeframe | `<TF>` |
| Fitness Score | `<SCORE>` |
| Net Profit | `<NET_PROFIT>` |
| Max Drawdown | `<MAX_DD>` |
| Profit Factor | `<PROFIT_FACTOR>` |
| Win Rate | `<WIN_RATE>` |
| Trades | `<TRADES>` |
| Safety Score | `<SAFETY_SCORE>` |

| Parameter | Value |
| --- | --- |
| `min_conf` | `<VALUE>` |
| `sl_atr_mul` | `<VALUE>` |
| `tp_atr_mul` | `<VALUE>` |
| `vol_mult` | `<VALUE>` |
| `max_daily_move_pct` | `<VALUE>` |
| `use_session` | `<VALUE>` |
| `session_time` | `<VALUE>` |
| `contracts` | `<VALUE>` |

### Rank 3

| Field | Value |
| --- | --- |
| Pair | `<PAIR>` |
| Timeframe | `<TF>` |
| Fitness Score | `<SCORE>` |
| Net Profit | `<NET_PROFIT>` |
| Max Drawdown | `<MAX_DD>` |
| Profit Factor | `<PROFIT_FACTOR>` |
| Win Rate | `<WIN_RATE>` |
| Trades | `<TRADES>` |
| Safety Score | `<SAFETY_SCORE>` |

| Parameter | Value |
| --- | --- |
| `min_conf` | `<VALUE>` |
| `sl_atr_mul` | `<VALUE>` |
| `tp_atr_mul` | `<VALUE>` |
| `vol_mult` | `<VALUE>` |
| `max_daily_move_pct` | `<VALUE>` |
| `use_session` | `<VALUE>` |
| `session_time` | `<VALUE>` |
| `contracts` | `<VALUE>` |

## Notes

- Forward window definition: `<FORWARD_SPLIT_RULE>`
- Data source: `<DATA_SOURCE>`
- Slippage model: `<SLIPPAGE_MODEL>`
- Survivorship / lookahead guard: `<GUARD_RATIONALE>`
- Final selection rule: keep only the strongest configurations with low drawdown and stable forward performance.

