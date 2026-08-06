# Decisions

- Analytics reads authoritative persisted closed Trade records; JournalEntry is an enriched,
  idempotent projection created from TradeClosed.
- Strategy name is resolved from strategy_version_id during journal projection and persisted as a
  historical snapshot; Feature 07 Trade is unchanged.
- Journal persistence uses NUMERIC(28,12) to match execution precision. The older
  context/database.md journal example still needs reconciliation in a documentation pass.
- MVP Sharpe is explicitly closed-trade daily Sharpe: UTC day buckets, zero-return gap days,
  zero risk-free rate, 365 annualization, and null for insufficient observations or zero variance.
- API image builds use HTTPS Debian archive sources with apt retries; HTTP package delivery
  repeatedly returned a same-sized but hash-mismatched binutils archive during Docker builds.
