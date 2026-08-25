# OANDA EUR/USD session-policy provenance

Policy identifier: `OANDA_FX_NY_V1`  
Retrieval date: **2026-08-24**  
Timezone: `America/New_York` (IANA; DST supplied by `zoneinfo`)  
Runtime effective interval: **OANDA_DOC_PENDING** (the implementation must
not be treated as documentary confirmation until the source pin is completed).

The V1 local schedule currently preserves the existing Atlas semantics:
weekly closure and the local `16:59`–`17:05` provider maintenance/rollover
window.  The empty, immutable exception table is the versioned location for
effective-dated holiday/session notices; absence of an exception is not an
inference from missing prices.

## Required source pins (TODO)

The worker must replace each placeholder with the actual OANDA document URL,
title, effective interval, and retrieval date, and add the relevant notice
identifier where applicable:

| Rule | URL | Title | Effective interval | Reason |
| --- | --- | --- | --- | --- |
| FX session calendar/trading hours | `OANDA_DOC_PENDING` | `OANDA_DOC_PENDING` | `OANDA_DOC_PENDING` | weekly closure |
| maintenance/rollover | `OANDA_DOC_PENDING` | `OANDA_DOC_PENDING` | `OANDA_DOC_PENDING` | provider maintenance/rollover |
| holiday/session exceptions | `OANDA_DOC_PENDING` | `OANDA_DOC_PENDING` | `OANDA_DOC_PENDING` | effective-dated exception |

Until this TODO is completed, do not claim documentary provenance is complete
or use an observed gap as evidence that a minute was unavailable.  An absent
minute during a policy-expected session remains an unexpected missing-data
failure (fail-closed).
