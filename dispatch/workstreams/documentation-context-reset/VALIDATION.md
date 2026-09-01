# Validation — Documentation and Context Reset

## Assignment

- **Role:** `VALIDATE`
- **Workstream:** `documentation-context-reset`
- **Branch:** `solo/documentation-context-reset`
- **CWD:** `/Users/vike/Desktop/atlas-documentation-context-reset`
- **Status:** `PASS`
- **Owned artifact:** this file
- **Specialist skills:** none

## Validation scope

Independently validate the completed T001 BUILD against the canonical PLAN and
task receipt. Do not modify application code, tests, fixtures, selectors,
harnesses, workflows, permanent documentation, or any PAPER/historical dispatch
artifact. This artifact is the only file the validator may write.

## Required evidence

1. Confirm `AGENTS.md` ≤100 lines and `DOMAIN.md` ≤120 lines.
2. Confirm all approved `CURRENT.md`, `memory.md`, `context/**`, and root
   placeholder deletions are absent.
3. Confirm `dispatch/ACTIVE.md`, `dispatch/COMPLETED.md`,
   `dispatch/MODEL-LOG.md`, historical root phase records, and existing
   workstreams are unchanged.
4. Scan active/current authority docs for stale references to deleted paths;
   historical dispatch references are allowed only when unchanged.
5. Verify README commands against the clean committed baseline's manifests,
   source tree, and migration layout.
6. Verify every DOMAIN law against committed-main implementation/test evidence,
   or confirm it is explicitly labeled as a future safety boundary.
7. Confirm `git diff --check` and exact diff scope; no application, test,
   schema, migration, frontend, PAPER, or unrelated configuration changes.
8. Report the clean worktree branch, base SHA, and preservation of the original
   dirty PAPER worktree without modifying either worktree.

## Result

**PASS** — T001 matches the canonical PLAN and its completion receipt. The
validation checkout is the approved documentation-only branch at the recorded
committed-main baseline.

## Evidence

### Identity and preservation

- `pwd` and `git rev-parse --show-toplevel` both resolve to
  `/Users/vike/Desktop/atlas-documentation-context-reset`.
- `git branch --show-current` → `solo/documentation-context-reset`.
- `git rev-parse HEAD`, `git rev-parse main`, and `git merge-base HEAD main` all
  return `e671190ae4a77282367f2cecfa27ef45a375add1`, matching PLAN §Current Git
  state and the T001 receipt.
- `git diff --quiet HEAD -- dispatch/ACTIVE.md dispatch/COMPLETED.md
  dispatch/MODEL-LOG.md dispatch/PHASE-*.md dispatch/workstreams` passed. The
  existing tracked dispatch records and historical workstreams are unchanged;
  the six approved empty root placeholders are the only dispatch deletions.
- The original `/Users/vike/Desktop/atlas` worktree remains on `main` at the
  same SHA. Its complete `git status --porcelain=v1 --untracked-files=all`
  output matches PLAN lines 69–137, including the dirty PAPER source, tests,
  migrations, dispatch artifacts, `.codegraph/.gitignore`, and
  `frontend/.env.local`. No operation modified that worktree.

### Inventory, limits, and stale paths

- `wc -l AGENTS.md DOMAIN.md README.md` → `81`, `51`, and `111`; the required
  AGENTS/DOMAIN limits (≤100/≤120) pass.
- `git diff --name-only --diff-filter=D` reports exactly `53` deletions:
  `45` paths under `context/`, `CURRENT.md`, `memory.md`, and the six planned
  root placeholders (`dispatch/ARCHITECTURE.md`, `DECISIONS.md`,
  `EXPLORATION.md`, `PLAN.md`, `REVIEW.md`, `TASKS.md`). Set comparison of
  `git ls-tree -r --name-only HEAD -- context` with the deleted context set is
  empty; all approved deletion paths are absent on disk and no other deleted
  path exists.
- `AGENTS.md`, `README.md`, `DOMAIN.md`, and `dispatch/ACTIVE.md` contain no
  references to deleted `context/`, `CURRENT.md`, `memory.md`, or placeholder
  paths. References found in unchanged historical dispatch records, and the
  inventory references in this workstream's PLAN/task receipt, are intentional
  and not active capability guidance.

### README command and capability audit

- README setup/migration claims match `.env.example`, `.python-version`,
  `pyproject.toml`, `alembic.ini`, `backend/persistence/migrations/`, and the
  tracked `package-lock.json`.
- README historical endpoints are present in the committed baseline:
  `backend/api/historical_data.py:103-254` and
  `backend/api/experiments.py:409-819`; the OANDA Practice historical adapter
  is `backend/integrations/oanda/source.py:196-260`.
- README application/validation commands match `package.json` scripts,
  `pyproject.toml` project/dev dependencies, `backend/runtime/main.py:17-55`,
  the frontend tree, and Playwright's tracked package dependency. The clean
  baseline migration list ends at `0021_experiment_deletion_lifecycle.py`.
- `backend/api/paper.py`, `backend/runtime/production.py`, and migrations
  `0022+` are absent from this checkout. README and AGENTS explicitly state
  PAPER/LIVE are not committed-main capabilities.

### DOMAIN evidence boundary

Current laws 1–9 are supported by committed-main source/tests, without using
the original dirty PAPER tree:

1. Immutable `StrategyVersion` identity/provenance: frozen domain value at
   `backend/domain/strategy.py:1466-1524`; source archive/fingerprint at
   `backend/strategies/fingerprint.py:22-48,84-133`; tests in
   `backend/tests/domain/test_primitives.py:416-433` and
   `backend/tests/strategies/test_provenance.py:36-49,109-133`.
2. Reproducible immutable Experiment inputs/results: configuration persistence
   at `backend/experiments/configuration.py:614-679`; completed-only and
   persisted-result reads at `backend/experiments/results.py:91-113,169-217`;
   immutable migration guards in `0004_phase_3_first_historical_trade.py`;
   result-state tests at `backend/tests/experiments/test_result_state.py:23-38`
   and `test_results.py:169-211`.
3. UTC, positive aligned ranges, and completed candles: `Bar` validation at
   `backend/domain/market_data.py:55-60,102-140`, configuration validation at
   `backend/experiments/configuration.py:330-334,389-403`, with tests in
   `backend/tests/experiments/test_configuration.py:85-99`.
4. Chronological/no-lookahead/one frontier evaluation: clock separation and
   exact entry lookup at `backend/experiments/clock.py:87-245`; frontier tests
   at `backend/tests/experiments/test_clock.py:161-215`.
5. Native M15 MID plus sparse M1 BID/ASK and no fabrication: OANDA fetches at
   `backend/integrations/oanda/source.py:236-260`; V2 coverage rejects
   unsupported/incomplete data at `backend/experiments/configuration.py:459-599`;
   contract tests in `backend/tests/market_data/test_snapshot_v2_contract.py`
   and `test_storage_coverage_v2.py`. The committed legacy V1 reader is
   explicitly isolated and labeled derived (`results.py:576-595`), while the
   current create path rejects non-V2 snapshots (`configuration.py:459-470`);
   it is not treated as current capability.
6. Pure Strategy boundary: `backend/strategies/contract.py:1-5,78-90,276-335`;
   registration/evaluation tests in `backend/tests/strategies/`.
7. Centralized Risk and sizing: `backend/risk/service.py:1-6,72-148` and
   `backend/tests/risk/test_service.py:44-99`.
8. Fill-derived Position and auditable execution provenance:
   `backend/execution/fill_application.py:1-5,74-243`, with the Fill-only
   transition test at `backend/tests/integration/test_fill_application.py:151-180`.
9. Fail-closed invalid/incomplete/unknown state: V2 coverage checks at
   `configuration.py:527-599`, result readiness/lineage checks at
   `results.py:103-113,275-288`, lifecycle failure persistence at
   `lifecycle.py:152-211`, and the passing non-integration diagnostic tests.

Laws 10–12 are under the explicitly titled `Future safety boundaries` section
(`DOMAIN.md:42-50`), so they make no current PAPER/LIVE implementation claim.

### Checks

- `git diff --check` passed.
- `uv run pytest -m "not integration and not external"` passed: `408 passed,
  4 skipped, 88 deselected` (four expected environment/health skips; four
  warnings). This is committed-main evidence only; no unfinished PAPER path
  was imported or used as authority.
- Tracked diff scope is exactly two approved rewrites plus the `53` approved
  deletions. The only untracked additions are approved `DOMAIN.md` and the
  three canonical documentation-context-reset workstream artifacts
  (`PLAN.md`, T001 receipt, and this `VALIDATION.md`); no application, test,
  fixture, selector, harness, workflow, schema, migration, frontend, PAPER, or
  unrelated configuration path changed.

## Findings / concerns

- No blocking findings.
- Non-blocking boundary note: committed-main retains an explicitly isolated
  legacy V1 derived-M15 read path for historical compatibility. The current
  V2 setup/creation path, README, and DOMAIN current-law wording do not present
  that legacy path as the supported workflow.
