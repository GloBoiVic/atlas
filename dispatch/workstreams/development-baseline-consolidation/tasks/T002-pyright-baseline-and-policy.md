# T002 - Pyright Baseline and Changed-Surface Policy

- **Workstream:** `development-baseline-consolidation`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Branch:** `solo/development-baseline-consolidation`
- **Base:** `611fe10b9b596f9e48339f305b99023d402c4514`
- **Dependency:** T001

## Outcome

Reconcile the contradictory Pyright history with current reproducible evidence and define
a temporary policy that exposes new typing regressions without pretending the repository-wide
baseline is clean.

## Scope

Primary artifacts:

- `dispatch/workstreams/development-baseline-consolidation/PYRIGHT.md`
- `AGENTS.md` when the temporary validation policy belongs in repository guidance

Required investigation and record:

- Exact Pyright version from the current locked environment.
- Exact current diagnostic count from structured Pyright output.
- Production versus test diagnostic counts.
- Dominant diagnostic rules and highest-concentration files.
- Exact command recorded by the historical validation that claimed repository-wide success.
- Whether Pyright configuration, dependency lock state, command scope, or source tree changed
  between that validation and current main.
- Whether the historical receipt was accurate, scoped differently, or incorrect.
- Unresolved root causes for the current debt, bounded for a later dedicated typing
  workstream.

Define and record the temporary policy:

- Touched production files introduce no new Pyright diagnostics.
- Touched tests introduce no diagnostics relative to their baseline.
- Focused typing checks are clean where an isolated clean surface exists.
- Repository-wide diagnostic count is recorded truthfully.
- No Pyright rule is disabled to make the baseline green.

## Constraints

- Do not perform a repository-wide typing cleanup.
- Do not disable rules, change the lockfile, change Pyright configuration solely to reduce
  the count, or alter application behavior.
- Use the current locked environment and structured output; distinguish command failures
  caused by diagnostics from command/runtime failures.

## Checks

Run the exact current and historical-comparison commands needed to support the record,
including focused checks for any touched production/test files. Record commands, counts,
and interpretation in `PYRIGHT.md` and this task receipt. Run `git diff --check`.

## Worker Evidence

BUILD execution completed. The investigation record is
`dispatch/workstreams/development-baseline-consolidation/PYRIGHT.md`.

## Immutable BUILD Receipt

- **Status:** `DONE`
- **Files changed:**
  - `dispatch/workstreams/development-baseline-consolidation/PYRIGHT.md`
  - `AGENTS.md`
  - `dispatch/workstreams/development-baseline-consolidation/tasks/T002-pyright-baseline-and-policy.md`
- **Checks/evidence:**
  - `uv run --frozen pyright --version` - `pyright 1.1.411`; the locked `uv.lock`
    package version is also `1.1.411`.
  - `uv lock --check` - passed; `Resolved 41 packages in 2ms`.
  - `uv run --frozen pyright backend --outputjson` - valid structured output,
    exit `1` for diagnostics, `214` files analyzed, `3,011` errors, `0` warnings,
    and `0` informations. Diagnostics split into `1,845` production and `1,166`
    test diagnostics across `25` and `27` files respectively.
  - Dominant rules were `reportUnknownArgumentType` `584`,
    `reportUnknownMemberType` `567`, `reportUnknownParameterType` `539`,
    `reportMissingParameterType` `528`, `reportArgumentType` `265`,
    `reportUnknownVariableType` `183`, `reportUnknownLambdaType` `87`, and
    `reportAttributeAccessIssue` `68`. The highest-concentration file was
    `backend/experiments/runner.py` with `861` diagnostics.
  - The exact historical success command, `uv run pyright backend`, was rerun and
    returned exit `1` with `3011 errors, 0 warnings, 0 informations`; stderr was
    empty. Valid diagnostic output distinguishes this from command/runtime failure.
  - `git diff --name-status e2ad47c5cbfbca89d58f915745f81180c4864db9
    611fe10b9b596f9e48339f305b99023d402c4514 -- pyproject.toml uv.lock backend`
    produced no output. The relevant Pyright configuration, lock state, command
    scope, and included backend source tree therefore show no tracked difference
    between the historical receipt base and current `main`.
  - Clean isolated probes passed for
    `backend/domain/strategy.py` plus `backend/strategies/contract.py`, and for
    `backend/tests/integrations/test_oanda_risk_projection.py`, each with `0`
    errors, warnings, and informations. No production or test file was touched by
    T002, so no touched-file baseline comparison was applicable.
  - An exploratory focused probe of
    `backend/persistence/strategy_repository.py` plus
    `backend/market_data/fingerprint.py` returned valid structured output with exit
    `1` and `7` errors. Those files were not touched by T002 and this was not used as
    a changed-surface gate.
  - `git diff --check` - passed with no whitespace errors after the T002 changes.
- **Findings/concerns:**
  - The historical PAPER Control receipt's `PASS - no type errors` claim is not
    reproducible or supportable as a repository-wide result. Its exact cause is
    unresolved because the receipt lacks raw output, tool version, exit status, and
    execution-environment details; no tracked config, lock, command-scope, or
    included-source difference explains it.
  - The truthful current repository-wide baseline remains `3,011` errors. The
    dominant unresolved causes are unknown-type propagation/missing annotations in
    experiment and market-data production paths and untyped fixtures/test doubles.
    A later dedicated typing workstream must address them; T002 performed no typing
    cleanup and disabled no rules.
  - No application, test, schema, migration, persisted-data, provider, trading,
    credential, runtime, or broker changes were made or used.
