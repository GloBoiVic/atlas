# Task 3 — Clock Abstraction

Create `backend/core/clock.py` with abstract `Clock.now() -> datetime`, `LiveClock`
returning `datetime.now(timezone.utc)`, and `SimulationClock` storing `_current_time`
with exact-assignment `advance(new_time)`.

Add deterministic tests proving simulation timestamps advance exactly. Use ABC and
abstractmethod. Commit and report to `.dispatch/task-3-report.md`.
