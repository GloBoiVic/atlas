# Dispatch Decisions

Feature 07 decisions approved during architecture alignment:

- Binance USDⓈ-M Futures `BTCUSDT` perpetual is the initial authenticated target.
- Isolated margin, 1× default leverage, 2× hard maximum, one-way mode.
- Different strategies may share an instrument; duplicate strategy/instrument bot instances
  are rejected.
- Virtual strategy exposure is netted into one broker position; opposing reductions use FIFO.
- Reversals are explicit reduce-only close then confirmed open.
- Atlas-managed reduce-only protective exits trigger on mark price.
- Futures-aware paper execution includes margin, funding, maintenance margin, and liquidation.
- Fees default to configurable 0.05% taker; funding is separate.
- Client IDs persist before submission; stream updates are reconciled against authoritative REST
  snapshots; unknown state blocks retries.
- Feature 07 excludes authenticated Binance connectivity; Feature 09 owns that adapter.
