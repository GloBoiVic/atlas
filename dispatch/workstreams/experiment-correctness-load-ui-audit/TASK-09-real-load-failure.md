# TASK-09 — Real V2 load terminal failure diagnosis

## Verdict

**DIAGNOSIS ONLY — no safe production fix identified.** The sole authorized real
OANDA Practice load remains terminal `FAILED` with `RUNTIME /
HISTORICAL_LOAD_FAILED`. It was not retried, reissued, repaired, or otherwise
contacted. No application code or other dispatch artifact was changed.

## Evidence reviewed

- `VALIDATION.md` records the one attempt: 205.855 seconds, 2 native M15 MID
  provider requests, 12 execution M1 BID/ASK requests, 63,402 inserted rows,
  one warm-up extension, durable progress at `Fetching M1 execution data` /
  `database_commit` with `1/1` ranges, and no snapshot.
- The failure occurred after the initial V2 execution commit callback and before
  `create_snapshot_v2` returned. The coordinator's outer handler classifies an
  otherwise unrecognized exception as the sanitized generic RUNTIME code. The
  durable record therefore does not preserve an exception type, traceback, or
  provider response detail from which a deterministic root cause can be proved.
- Read-only probes of the configured disposable databases found the dedicated
  `atlas_test` database reachable, but currently containing zero historical-load
  request rows. No partial request row or local log containing the missing
  exception was available to inspect. No secrets were printed or recorded.
- Source inspection covered the coordinator, V2 acquisition and incremental
  paths, OANDA native M15/MID and execution M1/BID/ASK fetch paths, progress
  persistence, and immutable V2 membership creation. The observed facts narrow
  the failure to the post-commit snapshot phase but do not safely distinguish a
  data-specific, database/provider-specific, or process/runtime exception.

## Focused verification

| Command | Result |
|---|---|
| `python -m pytest -q backend/tests/test_historical_data_load.py backend/tests/integrations/test_oanda_source.py` | **38 passed, 1 skipped** |
| `python -m compileall -q backend/market_data backend/integrations/oanda backend/persistence` | **Passed** |
| `ruff check` on the inspected load/OANDA/persistence modules and tests | **Passed** |

The available regression tests cover bounded provider windows, bounded
transport attempts, native M15 versus execution M1 separation, progress and
missing-only warm-up seams, and immutable snapshot behavior. They do not
reproduce the exact one-month provider response or the absent runtime traceback.

## Disposition

No fix is made. Adding speculative exception handling, retrying snapshot
creation, changing membership semantics, or altering the durable failure to
claim certainty would violate fail-closed behavior and could compromise native
M15 MID, independent M1 BID/ASK, or immutable snapshot guarantees.

Further investigation requires an explicitly authorized fresh run or preserved
local traceback/diagnostic from the original process. Any future real attempt
must be separately authorized; this artifact does not authorize one.
