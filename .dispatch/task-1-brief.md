# Task 1 — Shared AccountMode

Move the existing `AccountMode` enum from `backend/persistence/models.py` into
`backend/core/` so core events and persistence share one enum without either layer
depending on the other. Preserve values `paper`, `testnet`, and `production`.

Search all Python references and update imports. Do not change behavior beyond the
mechanical move. Run the full test suite immediately after the change. Commit the task.

Write a full report to `.dispatch/task-1-report.md`; return only status, commit hash,
tests, and concerns in the final response.
