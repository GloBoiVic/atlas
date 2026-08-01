# Atlas — Coding Standards

Project-wide coding conventions for Atlas. Every coding agent must follow these standards.

Read this file before writing any code.

---

## General Principles

1. **Simplicity over cleverness.** Write code that is easy to read and understand. Avoid clever one-liners that sacrifice clarity.

2. **Consistency over preference.** Follow existing patterns in the codebase. Don't introduce new patterns without strong justification.

3. **Explicit over implicit.** Don't rely on hidden behavior or magic. Make intent clear through naming and structure.

4. **Fail loudly.** Don't swallow errors silently. If something goes wrong, log it and propagate it.

5. **YAGNI.** You Ain't Gonna Need It. Don't build for future requirements. Build for what's needed now.

---

## Python Standards

### Style

- Follow PEP 8 for style
- Use `ruff` for linting and formatting — never run black, isort, or flake8 separately
- Maximum line length: 100 characters
- Use double quotes for strings
- Use trailing commas in multi-line structures

### Type Hints

```python
# Good
def calculate_position_size(
    balance: Decimal,
    risk_per_trade: float,
    stop_distance: Decimal,
) -> Decimal:
    risk_amount = balance * Decimal(str(risk_per_trade))
    return risk_amount / stop_distance

# Bad — no type hints
def calculate_position_size(balance, risk_per_trade, stop_distance):
    risk_amount = balance * risk_per_trade
    return risk_amount / stop_distance
```

**Rules:**
- Always use type hints on function signatures
- Use `X | None` for nullable types and built-in generics such as `list[X]` and `dict[K, V]`
- Use `UUID` for IDs, not `str`
- Use `Decimal` for backend money, prices, quantities, fees, and P&L. Float is allowed only for non-monetary ratios or bounded indicator calculations.

### Naming

```python
# Variables and functions — snake_case
candle_timestamp = clock.now()
def get_strategy_by_id(strategy_id: UUID) -> Strategy | None:

# Classes — PascalCase
class StrategyEngine:
    pass

# Constants — UPPER_SNAKE_CASE
DEFAULT_RISK_PER_TRADE = Decimal("0.01")
DEFAULT_TIMEFRAME = "1h"

# Private methods — leading underscore
def _calculate_risk(self, signal: Signal) -> Decimal:
    pass
```

**Rules:**
- Variables and functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_leading_underscore`
- Never use `camelCase` for Python code
- Never use single-letter variable names (except loop counters)

### Imports

```python
# Standard library
import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

# Third-party
import pandas as pd
import structlog
from fastapi import APIRouter
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

# Local
from backend.core.events import EventBus
from backend.risk.engine import RiskEngine
```

**Rules:**
- Always group imports: standard library → third-party → local
- Always use absolute imports, never relative
- Always import types at the top of the file
- Never use `from module import *`

### Error Handling

```python
# Good — specific exception handling
try:
    result = await broker.submit_order(order)
except ConnectionError as e:
    logger.error("broker_connection_failed", error=str(e), order_id=order.id)
    raise
except ExchangeError as e:
    logger.error("order_rejected", error=str(e), order_id=order.id)
    raise

# Bad — bare except
try:
    result = await broker.submit_order(order)
except:
    pass
```

**Rules:**
- Always catch specific exceptions, never bare `except:`
- Always log errors with context before re-raising
- Never swallow errors silently
- Always use `logger.exception()` for unexpected errors
- Never use exceptions for control flow

### Async/Await

```python
# Good
async def get_candles(instrument: str) -> list[Candle]:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return parse_candles(response.json())

# Bad — mixing sync and async
def get_candles(instrument: str) -> list[Candle]:
    response = requests.get(url)  # Blocking!
    return parse_candles(response.json())
```

**Rules:**
- Always use `async/await` for I/O operations
- Never mix sync and async code
- Never use `asyncio.run()` inside async functions
- Always use `async with` for context managers
- Never block the event loop
- Domain data providers return normalized Candle/Tick objects; use Pandas only inside bounded indicator or analysis calculations
- Use `asyncio.run()` only at synchronous process entrypoints, such as the worker `main()` function.
- Use `asyncio.get_running_loop()` inside running async code; do not use `asyncio.get_event_loop()` for new code.
- Long-running tasks must handle cancellation by cleaning up and re-raising `asyncio.CancelledError`.
- Keep explicit ownership of tasks created with `asyncio.create_task()` or `asyncio.TaskGroup`; do not create orphan tasks.
- Use `asyncio.gather()` only when its failure and cancellation behavior is intentional. Use `return_exceptions=True` when independent operations must report failures separately.
- Move unavoidable blocking library calls to an executor rather than running them on the event loop.

---

## TypeScript Standards

### Style

- Use ESLint and Prettier for formatting
- Maximum line length: 100 characters
- Use double quotes for strings
- Use semicolons
- Use trailing commas

### Type Safety

```typescript
// Good — explicit types
interface Strategy {
  id: string
  name: string
  parameters: Record<string, unknown>
}

function getStrategy(id: string): Promise<Strategy> {
  return api.get(`/strategies/${id}`)
}

// Bad — any type
function getStrategy(id: any): any {
  return api.get(`/strategies/${id}`)
}
```

**Rules:**
- Always use TypeScript interfaces for data shapes
- Never use `any` — use `unknown` if type is truly unknown
- Always use explicit return types on functions
- Use `string` for IDs, not `number`
- API monetary values remain serialized decimal strings; convert to `number` only at a controlled frontend display/chart boundary.

### Naming

```typescript
// Variables and functions — camelCase
const candleTimestamp = new Date()
function getStrategyById(id: string): Promise<Strategy> {

// Interfaces and types — PascalCase
interface Strategy {
  id: string
  name: string
}

// Constants — UPPER_SNAKE_CASE
const DEFAULT_RISK_PER_TRADE = 0.01
const DEFAULT_TIMEFRAME = "1h"

// React components — PascalCase
function DashboardPage() {
  return <div>Dashboard</div>
}
```

**Rules:**
- Variables and functions: `camelCase`
- Interfaces and types: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- React components: `PascalCase`
- Never use `snake_case` in TypeScript

### Imports

```typescript
// React/Next.js imports
import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"

// Shadcn components
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

// Local utilities
import { api } from "@/lib/api"
import { formatCurrency } from "@/lib/utils"
```

**Rules:**
- Always group imports: React/Next.js → third-party → local
- Always use `@/` path alias for local imports
- Always destructure imports when possible

### Error Handling

```typescript
// Good — specific error handling
try {
  const strategy = await api.get(`/strategies/${id}`)
  return strategy
} catch (error) {
  if (axios.isAxiosError(error)) {
    console.error("API Error:", error.response?.data)
  }
  throw error
}

// Bad — bare catch
try {
  const strategy = await api.get(`/strategies/${id}`)
  return strategy
} catch (error) {
  console.log(error)
}
```

**Rules:**
- Always handle errors in API calls
- Always use type narrowing for error types
- Never ignore errors silently
- Always show user-friendly error messages

---

## File Structure

### Backend

```
backend/
├── core/
│   ├── events.py          # EventBus and typed domain events
│   ├── clock.py           # Clock abstraction
│   ├── interfaces.py      # Abstract base classes
│   ├── errors.py          # Error types
│   └── logging.py         # Structured logging setup
├── data/
│   ├── provider.py        # DataProvider interface
│   ├── csv_provider.py    # CSV data provider
│   └── binance_provider.py # Binance data provider
├── strategy/
│   ├── engine.py          # Strategy engine
│   ├── base.py            # Strategy base class
│   └── examples/          # Example strategies
├── risk/
│   ├── engine.py          # Risk engine
│   └── config.py          # Risk configuration
├── execution/
│   ├── engine.py          # Execution engine
│   ├── broker.py          # Broker interface
│   ├── paper_broker.py    # Paper trading broker
│   └── binance_broker.py  # Binance broker adapter
├── journal/
│   ├── service.py         # Journal service
│   └── models.py          # Journal domain models
├── analytics/
│   ├── service.py         # Analytics service
│   └── metrics.py         # Performance metrics
├── backtester/
│   ├── engine.py          # Backtester engine
│   ├── simulation_clock.py # Simulation clock
│   └── models.py          # BacktestRun and BacktestTrade
├── health/
│   ├── monitor.py         # Health monitor
│   ├── models.py          # ComponentHealth, HealthStatus
│   └── circuit_breaker.py # Circuit breaker implementation
├── persistence/
│   ├── database.py        # Database connection
│   ├── models.py          # SQLAlchemy models
│   └── repositories/      # Repository abstractions
├── api/
│   ├── app.py             # FastAPI application
│   ├── deps.py            # Dependency injection
│   ├── routes/            # API routes
│   ├── schemas.py         # Pydantic models
│   └── websocket.py       # WebSocket handlers
└── config.py              # Application configuration
```

**Rules:**
- One class per file for major components
- Utility functions can share files
- Keep files under 300 lines — split if larger
- Always use `__init__.py` for package exports

### Frontend

```
frontend/
├── src/
│   ├── app/               # Next.js app router
│   │   ├── layout.tsx     # Root layout
│   │   ├── page.tsx       # Home page
│   │   ├── dashboard/
│   │   │   └── page.tsx
│   │   ├── strategies/
│   │   │   ├── page.tsx
│   │   │   └── [id]/
│   │   │       └── page.tsx
│   │   └── api/
│   │       └── .../route.ts
│   ├── components/
│   │   ├── ui/            # Shadcn components
│   │   ├── charts/        # TradingView chart wrappers
│   │   └── layout/        # Layout components
│   ├── lib/
│   │   ├── api.ts         # Axios API client
│   │   ├── utils.ts       # Utility functions
│   │   └── websocket.ts   # WebSocket client
│   └── types/
│       └── index.ts       # TypeScript interfaces
├── package.json
├── tsconfig.json
├── tailwind.config.ts
└── next.config.ts
```

**Rules:**
- One component per file
- Co-locate related components
- Keep components under 200 lines — extract if larger
- Always use TypeScript for all files

---

## Git Conventions

### Commit Messages

```
<type>: <description>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation change
- `style`: Code style change (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat: add SMA crossover strategy
fix: handle WebSocket reconnection failure
docs: update architecture diagram
test: add unit tests for risk engine
```

**Rules:**
- Always use imperative mood ("add" not "added")
- Always keep subject line under 50 characters
- Always use lowercase for type and description
- Never include a period at the end of the subject line

### Branches

```
main                    # Production branch
develop                 # Development branch
feature/xxx             # Feature branches
fix/xxx                 # Bug fix branches
```

**Rules:**
- Always branch from `develop`
- Always use descriptive branch names
- Always delete branches after merging

---

## Testing Standards

### Unit Tests

- Test one thing per test function
- Use descriptive test names that explain the scenario
- Always test both success and failure paths
- Never test implementation details — test behavior
- Use `setup_method` or fixtures for test setup

### Integration Tests

- Test complete workflows end-to-end
- Use real dependencies where possible
- Mock external services only when necessary
- Always clean up test data

### Test Coverage

- Minimum 80% coverage for core business logic
- 100% coverage for risk engine and execution engine
- No coverage requirements for UI components

### Test Commands

```bash
# Backend
pytest                          # Run all tests
pytest tests/test_strategy.py   # Run specific file
pytest -v                       # Verbose output
pytest --cov=backend            # With coverage

# Frontend
npm test                        # Run all tests
npm run test:watch              # Watch mode
```

---

## Documentation

### Code Comments

```python
# Good — explains WHY, not WHAT
# We use Decimal for prices because floating point arithmetic
# can cause precision issues with financial calculations
price = Decimal("1.23456")

# Bad — explains WHAT (obvious from code)
# Set price to 1.23456
price = Decimal("1.23456")
```

**Rules:**
- Comment on WHY, not WHAT
- Don't comment obvious code
- Always document public APIs
- Always document complex algorithms

### Docstrings

```python
def calculate_position_size(
    balance: Decimal,
    risk_per_trade: float,
    stop_distance: Decimal,
) -> Decimal:
    """
    Calculate position size based on risk parameters.

    Args:
        balance: Account balance
        risk_per_trade: Risk per trade as decimal (e.g., 0.01 for 1%)
        stop_distance: Distance from entry to stop loss in price units

    Returns:
        Position size in units of the instrument

    Raises:
        ValueError: If stop_distance is zero or negative
    """
    if stop_distance <= 0:
        raise ValueError("stop_distance must be positive")
    risk_amount = balance * Decimal(str(risk_per_trade))
    return risk_amount / stop_distance
```

**Rules:**
- Always document public functions
- Always include Args, Returns, and Raises sections
- Keep docstrings concise
- Update docstrings when changing function behavior

---

## Code Review Checklist

Before submitting code:

- [ ] Code follows style guidelines (ruff, ESLint)
- [ ] All tests pass
- [ ] Type hints are present on all function signatures
- [ ] Error handling is comprehensive
- [ ] No hardcoded values (use config)
- [ ] No sensitive data in code (API keys, passwords)
- [ ] Documentation is updated if needed
- [ ] Code is simple and readable
- [ ] No duplicated code
- [ ] No unused imports or variables

---

## Common Mistakes to Avoid

### Python

1. **Using `float` for money** — always use `Decimal`
2. **Bare `except:`** — always catch specific exceptions
3. **Blocking in async code** — always use `await`
4. **Relative imports** — always use absolute imports
5. **Missing type hints** — always add type hints

### TypeScript

1. **Using `any`** — always use `unknown` or proper types
2. **Missing error handling** — always handle API errors
3. **Client-side state for server data** — use React Query
4. **Inline styles** — use Tailwind classes
5. **Missing cleanup** — always clean up effects

### Architecture

1. **Trading logic in routes** — keep routes thin
2. **Direct database access in services** — use repositories
3. **Hardcoded configuration** — use config files
4. **Synchronous code in async context** — use async libraries
5. **Missing error propagation** — always log and re-raise
