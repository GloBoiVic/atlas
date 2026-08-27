# T014 — Sparse acquisition semantics

Status: `DONE_WITH_CONCERNS`

## Receipt

ROLE: BUILD  
STATUS: DONE_WITH_CONCERNS  
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T014-sparse-acquisition-semantics.md`  
FILES CHANGED: `backend/market_data/coverage.py`, `backend/market_data/ingestion.py`, `backend/persistence/models.py`, `backend/persistence/market_data_repository.py`, `backend/persistence/migrations/versions/0018_acquisition_windows.py`, `backend/tests/market_data/test_freeze03_regressions.py`  
CHECKS / EVIDENCE: CodeGraph-first audit; repository and branch verified. T013/ARCHITECTURE diagnosis classified all 1,293 gaps: M15 0; M1 1,293; closure 0; open-session 1,293; fully absent M1 1,293; missing-single-constituent 0; sampled provider failures/unknown 0; 38 sampled windows successful empty/sparse; 889 runs remain individually unclassified. Added durable acquisition-window provenance with successful empty/sparse reuse, retryable failure recording, sparse execution validity, and deterministic zero-repeat-call regression. Targeted tests: 34 passed; compileall and diff check passed. Live fresh full-year attempt against the configured PostgreSQL/OANDA environment: 415.126s, 0 M15 calls, 927 M1 calls, 927 successful sparse/empty windows persisted, 740,226 M1 rows, 24,605 M15 rows, no snapshot. Unchanged repeat planning recomputed 0 remaining M1 windows (zero provider calls) but snapshot completion exceeded the 180s worker timeout; no repeat snapshot metric is claimed.

CONCERNS: Full-year acquisition completed its provider/persistence phase, but snapshot materialization remains operationally incomplete; repeat provider-call evidence is structurally zero while snapshot completion timed out. Failure/unknown outcome rows are recorded with a narrow failure classification pending independent validation of all failure categories. No credentials are exposed.

Implement the architect-frozen distinction between successful provider-window
acquisition and M1 observation continuity. Classify the known 1,293 gaps by product,
closure, constituent, and window outcome; persist successful sparse/empty M1 window
provenance; make missing-only planning reuse such windows without re-querying; keep
native M15 analytical completeness strict; and create exact sparse M1 membership without
fabrication or forward-fill. Add deterministic regressions and preserve immutable
snapshot/fingerprint semantics. Then rerun genuine full-year load and unchanged repeat
evidence against the authorized disposable PostgreSQL/OANDA setup.
