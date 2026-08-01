# Task 6 — Structured Logging

Update `backend/core/logging.py` so structlog config is unconditional JSON with
TimeStamper(fmt="iso"), add_log_level, context/error processors, and JSONRenderer.
Ensure application modules use structlog.get_logger(), replacing stdlib logger use.
Errors must log contextual information before propagation or continuation.

Add or update focused tests for logging configuration/behavior where practical.

Commit and report to `.dispatch/task-6-report.md`.
