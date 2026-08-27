# T012 — Live coverage-gap remediation

Status: `DONE_WITH_CONCERNS`

Diagnose the 4,161 missing expected M1 minutes in the genuine
2025-01-01–2026-01-01 OANDA run. Determine whether the gaps are provider/session
closures, maintenance, malformed/incomplete observations, or a persistence/acquisition
defect. Correct only the authoritative session/coverage or acquisition behavior needed
to classify genuine unavailable intervals; do not loosen coverage, fabricate bars,
forward-fill, or hide gaps. Preserve immutable snapshots and add deterministic
regressions. Then use the authorized disposable database and rerun the genuine
full-year load and unchanged covered repeat, recording zero repeat provider calls if
valid coverage completes. Never expose credentials.

## Receipt

ROLE: BUILD  
STATUS: DONE_WITH_CONCERNS  
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T012-live-coverage-gap-remediation.md`  
FILES CHANGED: `backend/market_data/session_policy.py`; `backend/domain/market_data.py`; `backend/persistence/models.py`; `backend/persistence/migrations/versions/0017_session_policy_v2.py`; deterministic session/coverage tests; this receipt  
CHECKS / EVIDENCE: CodeGraph-first review; root and branch verified. The prior genuine run's 4,161 missing minutes were classified reproducibly: OANDA's published 2025 holiday notice explains 2,868 minutes (New Year's Day and Christmas/New Year's closures); 1,293 remain scattered expected-session gaps, with no closure anomalies or unexpected observations. Added effective-dated V2 holiday intervals for 2025-01-01, 2025-12-24/25, 2025-12-31 and the cross-year 2024-12-31 close. No bars were fabricated and validation was not loosened. Disposable `public` schema reset and `uv run alembic upgrade head` reached `0017_session_policy_v2 (head)`. Relevant tests: **90 passed, 2 skipped**; Ruff and `git diff --check` passed.  
CONCERNS: The genuine post-fix full-year rerun exceeded the 20-minute execution window before completion; it persisted 7,410 native M15 rows, 0 M1 rows, and 0 snapshots. No covered repeat or zero-provider-call proof is claimed. The remaining 1,293 pre-fix gaps are acquisition incompleteness, not provider/session closures; rerun completion remains required. Credentials were never printed or persisted.
