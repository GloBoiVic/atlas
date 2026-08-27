# T004 — V2 snapshot and Experiment path

Status: `DONE_WITH_CONCERNS`

After T001–T003, implement immutable deterministic V2 DatasetSnapshot membership and
fingerprinting over native M15 MID plus native M1 BID/ASK, and require both products
and warm-up for new Experiments. Ensure no M1→M15 derivation in the authoritative path,
preserve old snapshots/Experiments read-only, and quarantine stale V1/load authorities.
Add focused determinism, immutability, provenance, and no-lookahead tests.

## Receipt

Implemented the T004 V2 snapshot and Experiment validation slice only.

### Files changed

- `backend/market_data/ingestion.py` — V2 snapshot creation validates independent
  native M1 BID/ASK coverage, rejects invalid/duplicate membership, fingerprints
  the native execution contract, and reads native M15 membership directly for V2.
- `backend/experiments/configuration.py` — new Experiment validation requires
  immutable snapshot execution BID/ASK coverage in addition to completed native
  M15 warm-up/frontiers; it never derives analytical context from M1.
- `backend/domain/market_data.py` — added the explicit native M1 execution contract.
- `backend/tests/market_data/test_snapshot_v2_contract.py` — added descriptor
  immutability and native-vs-derived fingerprint tests.

### Checks and evidence

- Focused pytest — **8 passed, 5 skipped** (existing database-dependent cases).
- Ruff, compileall, and `git diff --check` — passed.

### Concerns / boundaries

- PostgreSQL-backed Experiment creation, immutable membership triggers, migration
  compatibility, and full end-to-end frontier validation remain for VALIDATE/T005.
- No benchmark suite or unrelated cleanup was added. Legacy V1 read/derivation
  remains available for compatibility and is not used by new V2 validation.
