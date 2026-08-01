# Supervisor Task 5 — Worker Integration and Docs

Review the completed supervisor slice for worker integration boundaries. Update the
worker entrypoint only enough to expose/inject supervisor lifecycle ownership without
inventing concrete trading pipelines or API endpoints. Update CURRENT.md and
context/features/02-core-infrastructure.md to reflect that BotSupervisor is implemented,
while health monitor and any remaining criteria stay deferred.

Add integration-focused tests for worker startup/shutdown wiring if appropriate. Run
pytest, Ruff, mypy, migration checks where available, and diff checks. Commit and write
the report to `.dispatch/supervisor-task-5-report.md`.
