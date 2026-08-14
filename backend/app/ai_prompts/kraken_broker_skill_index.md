# Kraken broker skill index (slim)

Format: `name — description — paper_ok|live_gated`

## paper
- `kraken-paper-strategy` — Test strategy logic on paper trading before touching live funds. — paper_ok
- `kraken-paper-to-live` — Promote a validated paper strategy to live trading with safety checks. — live_gated
- `recipe-paper-strategy-backtest` — Backtest a trading strategy using paper trading against live prices. — paper_ok

## spot
- `kraken-dca-strategy` — Dollar cost averaging with scheduled buys and performance tracking. — paper_ok
- `kraken-grid-trading` — Grid trading strategy with layered buy and sell orders across a price range. — paper_ok
- `kraken-multi-pair` — Monitor multiple trading pairs simultaneously for screening and comparison. — paper_ok
- `kraken-order-types` — Complete reference for all spot and futures order types and modifiers. — paper_ok
- `kraken-rebalancing` — Portfolio rebalancing to maintain target allocations across assets. — paper_ok
- `kraken-spot-execution` — Execute spot orders with validation, confirmation gates, and post-trade checks. — live_gated
- `kraken-stop-take-profit` — Manage stop-loss and take-profit orders for risk-bounded positions. — paper_ok
- `kraken-twap-execution` — Execute large orders as time-weighted slices to reduce market impact. — paper_ok
- `recipe-launch-grid-bot` — Deploy a grid trading bot with paper validation and live safety controls. — paper_ok
- `recipe-multi-pair-breakout-watch` — Monitor multiple pairs for price breakouts from defined ranges. — paper_ok
- `recipe-price-level-alerts` — Set up price level alerts that notify when key levels are crossed. — paper_ok
- `recipe-start-dca-bot` — Set up and run a dollar cost averaging bot from paper test to live. — paper_ok
- `recipe-track-orderbook-depth` — Monitor order book depth and bid-ask imbalance for liquidity signals. — paper_ok
- `recipe-trailing-stop-runner` — Ride a trend with a trailing stop that locks in profits on reversal. — paper_ok
- `recipe-weekly-rebalance` — Run a weekly portfolio rebalance to maintain target asset allocations. — paper_ok

## futures
- `kraken-basis-trading` — Capture the spot-futures price spread with delta-neutral basis trades. — paper_ok
- `kraken-funding-carry` — Earn funding rate payments by positioning on the paying side of perpetuals. — paper_ok
- `kraken-funding-ops` — Manage deposits, withdrawals, and wallet transfers safely. — live_gated
- `kraken-futures-risk` — Futures-specific risk management: leverage, funding rates, margin, and liquidation awar... — paper_ok
- `kraken-futures-trading` — Place, manage, and monitor futures orders across the full lifecycle. — live_gated
- `kraken-liquidation-guard` — Prevent futures liquidation through margin monitoring and emergency procedures. — paper_ok
- `recipe-basis-trade-entry` — Enter a spot-futures basis trade when the premium exceeds a target threshold. — paper_ok
- `recipe-funding-rate-scan` — Scan perpetual contracts for attractive funding rate carry opportunities. — paper_ok
- `recipe-futures-hedge-spot` — Hedge a spot holding with a short futures position to lock in value. — paper_ok

## risk
- `kraken-alert-patterns` — Price alerts, threshold monitoring, and notification triggers for agents. — paper_ok
- `kraken-autonomy-levels` — Progress from manual trading to full agent autonomy with controlled risk at each level. — live_gated
- `kraken-error-recovery` — Handle order failures, network errors, and duplicate submissions safely. — paper_ok
- `kraken-fee-optimization` — Minimize trading fees through maker orders, volume tiers, and fee-aware execution. — paper_ok
- `kraken-rate-limits` — Understand Kraken API rate limits and adapt agent behavior when limits are hit. — paper_ok
- `kraken-risk-operations` — Operational risk controls for live agent trading sessions. — paper_ok
- `recipe-drawdown-circuit-breaker` — Automatically stop trading when portfolio drawdown exceeds a threshold. — paper_ok
- `recipe-emergency-flatten` — Cancel all orders and close all positions in an emergency. — live_gated
- `recipe-fee-tier-progress` — Track 30-day trading volume progress toward the next fee tier. — paper_ok

## earn
- `kraken-earn-staking` — Discover staking strategies, allocate funds, and track earn positions. — paper_ok
- `recipe-earn-yield-compare` — Compare earn strategy yields across assets and lock types to find the best rate. — paper_ok

## recipes
- `recipe-daily-pnl-report` — Generate a daily profit and loss summary from trades and balances. — paper_ok
- `recipe-morning-market-brief` — Generate a morning market summary with prices, volume, and portfolio state. — paper_ok
- `recipe-portfolio-snapshot-csv` — Export a portfolio snapshot with balances and valuations to CSV. — paper_ok
- `recipe-subaccount-capital-rotation` — Rotate capital between subaccounts based on strategy performance. — paper_ok
- `recipe-withdrawal-to-cold-storage` — Safely withdraw funds to a pre-approved cold storage address. — live_gated

## platform
- `kraken-market-intel` — Read market state with low-noise data pulls and streaming updates. — paper_ok
- `kraken-mcp-integration` — Connect MCP clients to kraken-cli for native tool calling without subprocess wrappers. — paper_ok
- `kraken-portfolio-intel` — Portfolio analysis, P&L tracking, trade history, and export reports. — paper_ok
- `kraken-setup` — Install kraken-cli, create API credentials, and go from paper trading to live in under ... — paper_ok
- `kraken-shared` — Shared runtime contract for kraken-cli: auth, invocation, parsing, and safety. — paper_ok
- `kraken-subaccount-ops` — Create and manage subaccounts with inter-account transfers. — paper_ok
- `kraken-tax-export` — Export trade history, ledgers, and cost basis data for tax reporting. — paper_ok
- `kraken-ws-streaming` — Real-time data streaming via WebSocket for spot and futures. — paper_ok
