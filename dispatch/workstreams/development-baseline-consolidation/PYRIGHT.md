# Pyright Baseline Investigation

- **Workstream:** `development-baseline-consolidation`
- **Task:** `T002`
- **Role:** `BUILD`
- **Captured:** `2026-09-10`
- **Repository baseline:** `611fe10b9b596f9e48339f305b99023d402c4514`

## Scope

This record reconciles the historical repository-wide Pyright success claim with
the current locked environment. Pyright is configured by `pyproject.toml` with
`include = ["backend"]` and `typeCheckingMode = "strict"`; production means
`backend` excluding `backend/tests`, and tests mean `backend/tests`.

No application or test source was changed for T002. No Pyright rule, configuration,
dependency lock, schema, migration, persisted data, or trading behavior was changed.

## Reproducible Commands

Run from the repository root:

```bash
uv lock --check
uv run --frozen pyright --version

set +e
uv run --frozen pyright backend --outputjson > /tmp/atlas-pyright.json 2> /tmp/atlas-pyright.stderr
rc=$?
set -e
printf 'pyright_exit=%s\n' "$rc"
jq -r '
  "version=" + .version,
  "files_analyzed=" + ((.summary.filesAnalyzed // 0) | tostring),
  "errors=" + ((.summary.errorCount // 0) | tostring),
  "warnings=" + ((.summary.warningCount // 0) | tostring),
  "informations=" + ((.summary.informationCount // 0) | tostring),
  "diagnostics=" + ((.generalDiagnostics | length) | tostring)
' /tmp/atlas-pyright.json
```

The locked-environment outputs were:

- `uv lock --check` - `Resolved 41 packages in 2ms`.
- `uv run --frozen pyright --version` - `pyright 1.1.411`. Pyright also printed its
  non-failing notice that `1.1.414` is available.
- Structured command exit: `1`.
- Structured JSON: version `1.1.411`, `214` files analyzed, `3,011` diagnostics,
  all `3,011` errors, `0` warnings, and `0` informations.
- The structured output parsed successfully and the command stderr was empty. The
  exit status is therefore a diagnostic result, not a Pyright, `uv`, or runtime
  invocation failure.

The exact historical command was also rerun without `--frozen`:

```bash
uv run pyright backend
```

It returned exit status `1`, produced `3011 errors, 0 warnings, 0 informations`,
and had empty stderr. This confirms that the lock-enforced structured run and the
historical command scope agree in the current checkout.

The structured report was grouped with this command to establish the rule and file
concentrations:

```bash
jq -r '
  "rules:",
  ([.generalDiagnostics[] | (.rule // "(no rule)")] | group_by(.)
   | map({rule: .[0], count: length}) | sort_by(-.count)[:8][]
   | "\(.count)\t\(.rule)"),
  "top_files:",
  ([.generalDiagnostics[] | .file] | group_by(.)
   | map({file: .[0], count: length}) | sort_by(-.count, .file)[:10][]
   | "\(.count)\t\(.file)")
' /tmp/atlas-pyright.json
```

## Current Counts

| Scope | Diagnostic files | Errors | Warnings | Informations |
| --- | ---: | ---: | ---: | ---: |
| Repository (`backend`) | 52 | 3,011 | 0 | 0 |
| Production (`backend` excluding tests) | 25 | 1,845 | 0 | 0 |
| Tests (`backend/tests`) | 27 | 1,166 | 0 | 0 |

Dominant diagnostic rules:

| Count | Rule |
| ---: | --- |
| 584 | `reportUnknownArgumentType` |
| 567 | `reportUnknownMemberType` |
| 539 | `reportUnknownParameterType` |
| 528 | `reportMissingParameterType` |
| 265 | `reportArgumentType` |
| 183 | `reportUnknownVariableType` |
| 87 | `reportUnknownLambdaType` |
| 68 | `reportAttributeAccessIssue` |

The top eight rules account for `2,821` of `3,011` diagnostics. The highest-
concentration files are:

| Count | File |
| ---: | --- |
| 861 | `backend/experiments/runner.py` |
| 263 | `backend/market_data/freeze03_benchmark.py` |
| 221 | `backend/tests/market_data/test_freeze03_regressions.py` |
| 165 | `backend/tests/experiments/test_price_analysis_results.py` |
| 148 | `backend/tests/test_historical_data_load.py` |
| 146 | `backend/market_data/historical_load.py` |
| 127 | `backend/tests/experiments/test_results.py` |
| 122 | `backend/tests/runtime/test_runtime_activation.py` |
| 90 | `backend/api/historical_data.py` |
| 88 | `backend/tests/integration/test_api_experiments.py` |

## Historical Comparison

The historical success claim is in
`dispatch/workstreams/paper-control-01-trader-activation-supervision/VALIDATION.md`,
committed with `319ed6317df4e1025cd13e2b1c7c3b330d43bed4`. That receipt records
`e2ad47c5cbfbca89d58f915745f81180c4864db9` as its base and lists this exact check:

```text
uv run pyright backend | PASS - no type errors; tool update notice only
```

Other historical records show that the result was not stable as a repository-wide
claim:

| Record | Command/result |
| --- | --- |
| `paper-06-runtime-activation/remediations/R005.../VALIDATION.md` | `uv run pyright backend` - `2,987 errors` |
| `dogfood-02-protected-trade-lifecycle-closure/VALIDATION.md` | `uv run pyright backend --level error` - `3,011 errors` |
| `ui-03-paper-trade-outcome-visibility/VALIDATION.md` | Full backend Pyright - `3,011 errors` |
| `experiment-foundation-recovery/VALIDATION-R2.md` | `python -m pyright` - `2,036 errors`; older source state and different invocation |

The direct comparison between the historical receipt's recorded base and current
`main` is:

```bash
git diff --name-status e2ad47c5cbfbca89d58f915745f81180c4864db9 \
  611fe10b9b596f9e48339f305b99023d402c4514 -- pyproject.toml uv.lock backend
```

It produced no output. In particular:

- The Pyright configuration is unchanged. Its relevant settings remain strict
  checking over `backend`, the `.venv` at the repository root, disabled missing-stub
  and unused-function reports, and the test execution-environment relaxations for
  unknown variable and member types.
- `uv.lock` is unchanged and pins Pyright to `1.1.411`; its project requirement
  remains `pyright>=1,<2`. The current SHA-256 values are
  `pyproject.toml` `a3d4786220a96826ef378d37ba429cc21b2d18e4b8748be6807a8ee11d12f225`
  and `uv.lock` `6ca10d2501026ba30fed7ceed0a81225499297f3e225e7912023ee7ec83604b9`.
- The Pyright-included production/test source tree under `backend` is unchanged.
  The intervening commits changed frontend and dispatch files, but those are outside
  the configured Pyright include path.
- The historical success command and the current reproduction both target
  `backend`. The current locked run adds only `--frozen` and `--outputjson` for
  environment enforcement and structured evidence.

### Interpretation

The historical `PASS` is not an accurate, reproducible repository-wide success
receipt for the recorded command and source baseline. It is contradicted by the
current rerun, by later records reporting `2,987` and `3,011` errors, and by the
absence of any relevant config, lock, command-scope, or included-source difference
between the receipt's base and current `main`.

The precise cause of the historical green result cannot be established from the
receipt. It records no raw output, Pyright version, exit status, or execution
environment. An alternate environment or working tree, stale/partial output, or
incorrect status interpretation remains possible, but is not asserted as fact.

## Bounded Unresolved Causes

The current evidence supports a typing-debt characterization, not a completed root-
cause analysis:

- The dominant pattern is unknown-type propagation and missing annotations. The
  leading four rules alone account for `2,218` diagnostics.
- Production concentration is highest in the historical experiment/market-data
  path, especially `backend/experiments/runner.py` with `861` diagnostics and
  `backend/market_data/freeze03_benchmark.py` with `263`.
- Test concentration is dominated by untyped fixtures, callbacks, and test doubles;
  current examples include missing fixture parameter types and unknown arguments.
- The remaining argument/member mismatches, optional-access issues, and unused
  symbols need separate ownership and should not be inferred away from this count.

These observations bound a later dedicated typing workstream. T002 does not annotate
the repository, remove diagnostics, or decide whether any rule should change.

## Temporary Changed-Surface Policy

- Run focused structured Pyright for the exact touched production/test Python files
  in the locked environment before and after a change.
- A touched production file may add no diagnostic relative to its recorded pre-change
  baseline. A touched test file may likewise add no diagnostic relative to its
  test-file baseline. Record the baseline and post-change counts and any added
  diagnostic rule/message/location.
- Require zero diagnostics for a focused surface when that surface is independently
  isolated and clean; do not treat a broad import graph's unrelated diagnostics as a
  reason to disable a rule.
- Record the repository-wide diagnostic count truthfully as a separate baseline
  measurement. A valid JSON report with exit `1` is a diagnostic result; invalid or
  missing output and `uv`/tool/runtime failures are separate failures.
- Do not disable Pyright rules or change Pyright configuration or lock state to make
  the repository-wide baseline green.

For T002, no production or test files were touched, so no touched-file baseline
comparison was applicable. Clean isolated probes were nevertheless verified:

```text
uv run --frozen pyright backend/domain/strategy.py backend/strategies/contract.py --outputjson
  exit 0; 0 errors, 0 warnings, 0 informations
uv run --frozen pyright backend/tests/integrations/test_oanda_risk_projection.py --outputjson
  exit 0; 0 errors, 0 warnings, 0 informations
```

An exploratory probe of two older reported-clean files,
`backend/persistence/strategy_repository.py` and `backend/market_data/fingerprint.py`,
returned `7` errors under the current tree. Those files were not touched by T002 and
the result is not used as a changed-surface gate.

## Safety And Scope

No application behavior, schemas, migrations, persisted data, provider behavior,
trading semantics, credentials, runtime process, or broker operation was changed or
used. No repository-wide typing cleanup was performed.
