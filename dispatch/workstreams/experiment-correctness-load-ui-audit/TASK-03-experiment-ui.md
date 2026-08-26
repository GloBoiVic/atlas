# TASK-03 Receipt — Experiment setup and results UI

## Scope completed

- Simplified primary Experiment setup language to Strategy, Period, Data, Strategy settings, Starting capital, Risk per trade, Trading costs, and Run Experiment.
- Removed the fixed-duration and polling-frequency promise from the setup flow.
- Added truthful known/unknown durable load progress treatment: determinate progress is shown only when the API supplies a valid total; otherwise progress is explicitly indeterminate.
- Moved price analysis and assumptions/provenance behind progressive Technical details / disclosure sections while preserving failed and zero-Trade semantics.
- Hid snapshot fingerprints and policy identifiers from normal snapshot labels; technical facts remain available in technical disclosure.
- Standardized Experiment list/detail formatting for percentages and ratios, explicitly labelled Max Drawdown (%), and disclosed canonical drawdown amount alongside percent.

## Required references inspected

- `context/design/design.md`
- `context/design/visual-guide.md`
- `context/design/ui-tokens.md`
- `context/design/atlas-experiment-run-page.png`
- `context/design/atlas-experiments-detail-page.png`
- `context/design/atlas-experiments-page.png`
- `dispatch/ACTIVE.md`, `PLAN.md`, `ARCHITECTURE.md`, `EXPLORATION.md`, `READY.md`
- `TASK-01-results.md`, `TASK-02-historical-load.md`
- `context/features/experiments.md`, `context/features/experiment-results.md`, `context/features/historical-data.md`
- `context/architecture/domain-model.md`, `context/architecture/safety-model.md`

## Changed application files

- `frontend/components/experiment-workflow.tsx`
- `frontend/tests/experiment_list.test.tsx`

No backend contracts, generated clients, Strategy rules, dependencies, PAPER/LIVE behavior, comparison screens, or other dispatch artifacts were changed.

## Validation evidence

- `npm run test:web -- --run tests/experiment_results.test.tsx tests/experiment_list.test.tsx` — **6 passed**.
- `npm run typecheck:web` — **passed**.
- `npx eslint frontend/components/experiment-workflow.tsx frontend/tests/experiment_results.test.tsx frontend/tests/experiment_list.test.tsx` — **passed with no errors or warnings**.
- `npx prettier --check ...` reports existing formatting divergence in `experiment-workflow.tsx`; no application behavior or contract issue was identified. No Git commands were run.
