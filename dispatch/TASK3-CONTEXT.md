# Task 3 context aggregation decision

The aggregator retains the newest valid book and mark component independently,
but publishes nothing until both components are present, belong to the same
instrument, have UTC timestamps, and are within their injected freshness windows
relative to one injected clock reading. A future-dated component is suppressed.
Crossed, non-positive, non-finite, malformed-time, and out-of-order updates are
suppressed without replacing the retained valid component. A stale retained
component remains available for recovery, but cannot participate in a publication
until a newer update makes the pair fresh again.

Aggregation is synchronous and creates no tasks. Each successful update returns
the existing immutable `MarketContextUpdated` event; the later Feature 08 runner
owns EventBus publication. `as_of` is the clock reading used for the decision,
while each component timestamp is carried independently on `MarketContext`.
Index price and funding rate are transported facts only; no settlement, P&L,
liquidation, trigger, fill, or PaperBroker behavior belongs here.
