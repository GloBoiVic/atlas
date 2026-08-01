# Task 4 — Configuration System

Update `backend/config.py` using Pydantic v2 SettingsConfigDict while preserving the
existing uppercase Settings interface. Keep deployment validation strict for paper,
testnet, and production.

Add typed YAML models for strategy (name, parameters), risk (max_open_positions,
per_trade_risk), and broker (name, mode). Add `config/default.yaml` and
`load_config(path=Path("config/default.yaml"))`. Expand `${VAR_NAME}` before
validation and fail clearly for missing variables, missing files, malformed YAML,
missing sections, or invalid modes. Keep Settings and YAML config separate. Use the
existing ConfigError taxonomy. Add PyYAML dependency and tests.

Commit and report to `.dispatch/task-4-report.md`.
