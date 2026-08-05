# Decisions

## Feature 08 scope revision

- Confirmed by human: Feature 08 targets Binance **USDⓈ-M Futures**, not Spot.
- Rationale: the product should support buying/going long and selling/going short
  futures contracts without requiring ownership of spot crypto assets.
- Use `binance_usdm` provider identity and Binance `fstream` public streams.
- Use `@aggTrade`, `@bookTicker`, and `@markPrice@1s` in addition to completed
  `@kline` streams.
- Keep historical Binance Spot data and its provider identity unchanged.
- Feature 08 transports normalized futures market context; Feature 09 owns mapping
  it into Feature 07 paper execution and any funding settlement policy.
- COIN-M, authenticated execution, and delivery contracts remain deferred.

## Feature 08 live provider registry

- Keep live-provider composition separate from historical-provider composition.
- Store side-effect-free factories and create a fresh provider per lookup so feed sessions do
  not share subscriptions or candle deduplication state.
- Register `binance_usdm` only; registration does not construct a network connection.
