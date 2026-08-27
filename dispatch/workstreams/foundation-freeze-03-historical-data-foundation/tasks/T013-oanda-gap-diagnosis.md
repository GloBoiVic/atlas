# T013 — OANDA gap diagnosis and completion

Status: `BLOCKED`

Diagnose the scattered 1,293 expected-session M1 gaps after T012. Inspect exact gap
locations and provider request boundaries/response counts to determine whether the
cause is pagination overlap/omission, rate-limit/retry loss, provider sparse data, or
incorrect session classification. Correct authoritative acquisition/session logic only
when evidence supports it; never fabricate, forward-fill, or weaken coverage. Then
reset the authorized disposable DB if needed, migrate through head, complete the
genuine 2025 full-year load and unchanged covered repeat with zero provider calls, or
document a precise provider-data blocker.

## Receipt

ROLE: BUILD  
STATUS: BLOCKED  
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T013-oanda-gap-diagnosis.md`  
FILES CHANGED: this receipt only  
CHECKS / EVIDENCE: CodeGraph-first source audit; CWD/repository/branch verified. The
current disposable PostgreSQL database was queried without exposing credentials. Its
current V2 rows are 370,113 M1 BID and 370,113 M1 ASK observations, 24,605 native M15
MID observations, with 0 snapshots. Recomputing the unchanged V2 policy over
`[2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z)` gives 1,293 missing expected minutes in
927 scattered runs (not closure anomalies and not unexpected observations). The first
20 run locations include `2025-01-01T22:33Z`, `2025-01-02T22:39Z/22:52Z`,
`2025-01-03T21:12Z`, and `2025-01-08T06:02Z`; the final runs include
`2025-12-28T22:27Z–22:50Z`, `2025-12-29T22:21Z`, and
`2025-12-30T21:24Z/23:21Z`. The gaps span every month and are concentrated, but not
limited to, the post-rollover local 17:00 hour (1,076 minutes); they are not a single
request boundary or one holiday interval.

The acquisition boundary is exact and unchanged: `_windows` emits contiguous
half-open windows, M1 windows are 4,000 minutes, and `_fetch` drops provider candles
outside `[window_start, window_end)`. `_request` sends `from`, `to`, `price=BA`,
`granularity=M1`, and `smooth=false`; it does not paginate by response count or send an
explicit `includeFirst`. Existing deterministic tests cover the 4,000-minute split,
boundary filtering, duplicate collapse/conflict rejection, and retry behavior.

Credentialed live diagnosis sampled 38 deterministic missing runs (first/last ten and
every 50th run): all 38 returned HTTP 200, one attempt, and zero candles for the
requested missing interval. Six representative targets were then fetched in widened
11-minute windows (five minutes before through six after): each still returned zero
target candles while returning surrounding candles. The same six targets fetched with
`price=MBA` also returned no target component. This rules out boundary omission,
includeFirst behavior, pagination-window overlap, and BID/ASK-only normalization as
the cause. The sample showed no rate-limit/retry event. The prior unchanged full-year
repeat made 927 M1 calls, matching the 927 remaining missing runs; it produced no
snapshot and no zero-call covered repeat.

CONCERNS: Evidence supports provider-sparse historical candles (including recurring
post-rollover sparsity), not an acquisition or session-policy defect. No bars were
fabricated, forward-filled, or coverage rules loosened; no narrow source fix is
justified. A valid alternate one-year range was not established: the observed gaps span
the entire requested calendar year, so selecting a different range without a fresh
full-year acquisition and proof would be unsupported. The unchanged live full-year
path therefore remains blocked and no deterministic regression was added because the
existing request-boundary/duplicate/retry regressions already pass.
