# Library Docs

Project-specific usage patterns for every third-party library in Atlas. This file only covers how we use each library in this specific project — rules, patterns, and constraints specific to Atlas.

Read the relevant section before implementing any feature that touches these libraries.

---

## Before Using Any Library

Before implementing any feature that uses a third party library:

1. **Read this file** for project-specific patterns and boundaries.

2. **Check the architecture context file** for how the component fits into the system.

3. **Check the feature file** for acceptance criteria and technical details.

4. **Read the relevant local skill** under `.agents/skills/` for detailed library patterns.

5. **Verify version-sensitive APIs** against the declared/resolved dependency version and
   official documentation or changelog before implementing them.

The order of authority is:

```
Security/product/architecture invariants → Feature file → Manifest/lockfile → Official
versioned docs → This file → Local skills → General training knowledge
```

Never rely on general training knowledge alone for library APIs — they change frequently and training data may be outdated.

---

## FastAPI

Reference skill: `.agents/skills/fastapi/SKILL.md`. Dependency injection details:
`.agents/skills/fastapi-dependency-injection/SKILL.md`.

### App Setup

```python
# backend/api/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Atlas", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Route Structure

```python
# backend/api/routes/strategies.py
from typing import Annotated

from fastapi import APIRouter, Depends

router = APIRouter(prefix="/strategies", tags=["strategies"])
StrategyServiceDep = Annotated[StrategyService, Depends(get_strategy_service)]

@router.get("/")
async def list_strategies(service: StrategyServiceDep) -> list[StrategyRead]:
    return await service.list_active()

@router.post("/")
async def create_strategy(
    config: StrategyCreate,
    service: StrategyServiceDep,
) -> StrategyRead:
    return await service.register(config)
```

Routes remain thin. Services own business logic and repositories own database access.

### Dependency Injection

```python
# backend/api/deps.py
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from backend.persistence.database import async_session

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session

# Transaction commit/rollback ownership must be explicit at the service/repository
# boundary. Do not add commits to routes or hide trading-state transitions in DI.
```

### WebSocket

```python
# backend/api/websocket.py
from fastapi import WebSocket, WebSocketDisconnect

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict[str, object]) -> None:
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

### Rules

- Prefer `Annotated[..., Depends(...)]` aliases for reusable dependencies. Database sessions are
  created by the dependency boundary — never create sessions directly in routes.
- Always use `APIRouter` for route groups — never add routes directly to `app`
- Always handle errors gracefully — return proper HTTP status codes
- Always use Pydantic v2 models for request/response validation and explicit route return types
- Routes are thin — business logic goes in services, not routes
- Never put trading logic in routes

---

## SQLAlchemy

Reference skill: `.agents/skills/sqlalchemy-orm/SKILL.md`. Atlas uses SQLAlchemy 2.0's typed
ORM API; do not copy legacy `Column`-based examples from older documentation.

### Base Model

```python
# backend/persistence/models.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
```

### Model Example

```python
# backend/persistence/models.py
from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

class Strategy(Base, TimestampMixin):
    __tablename__ = "strategies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entrypoint: Mapped[str] = mapped_column(String(500), nullable=False)
    repository: Mapped[str] = mapped_column(String(500), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
```

### Async Session

```python
# backend/persistence/database.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
```

### Query Patterns

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Get by ID
result = await session.execute(select(Strategy).where(Strategy.id == strategy_id))
strategy = result.scalar_one_or_none()

# Get all with filter
result = await session.execute(
    select(Strategy).where(Strategy.is_active.is_(True)).order_by(Strategy.created_at.desc())
)
strategies = list(result.scalars().all())

# Create
strategy = Strategy(
    name="sma_crossover",
    entrypoint="sma_crossover",
    repository="git@github.com:private/atlas-strategies.git",
    commit_sha="<pinned-commit>",
)
session.add(strategy)
await session.commit()
await session.refresh(strategy)
```

### Rules

- Always use async sessions (`AsyncSession`) — never synchronous sessions
- Always use `expire_on_commit=False` in session factory
- Always use `select()` style queries — never `session.query()`
- Always commit and refresh after create/update
- Never use `session.execute(text(...))` — always use ORM queries
- Models use UUID primary keys — never auto-increment integers
- Models use `TIMESTAMP WITH TIME ZONE` — never naive timestamps

---

## Alembic

### Generate Migration

```bash
# After changing models
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View current version
alembic current
```

### Migration File

```python
# alembic/versions/xxxx_description.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'strategies',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('entrypoint', sa.String(500), nullable=False),
        sa.Column('repository', sa.String(500), nullable=False),
        sa.Column('commit_sha', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table('strategies')
```

### Rules

- Always generate migrations after model changes — never modify schema manually
- Always include both `upgrade()` and `downgrade()` functions
- Always test migrations roll back cleanly
- Never use `op.execute()` for data migrations in schema migrations

---

## Pandas

### OHLC Data

```python
import pandas as pd

# Load candles into DataFrame
df = pd.DataFrame([candle.__dict__ for candle in candles])
df.set_index("timestamp", inplace=True)

# Calculate SMA
df["sma_fast"] = df["close"].rolling(window=fast_period).mean()
df["sma_slow"] = df["close"].rolling(window=slow_period).mean()

# Calculate Bollinger Bands
df["bb_middle"] = df["close"].rolling(window=20).mean()
df["bb_std"] = df["close"].rolling(window=20).std()
df["bb_upper"] = df["bb_middle"] + (df["bb_std"] * 2)
df["bb_lower"] = df["bb_middle"] - (df["bb_std"] * 2)
```

### Signal Generation

```python
# Generate buy/sell signals
df["signal"] = 0
df.loc[df["sma_fast"] > df["sma_slow"], "signal"] = 1  # Buy
df.loc[df["sma_fast"] < df["sma_slow"], "signal"] = -1  # Sell

# Detect crossovers
df["crossover"] = df["signal"].diff()
```

### Rules

- Use normalized `Candle` objects at domain boundaries; Pandas may be used internally for indicator calculations
- Always set timestamp as index for time-series operations
- Use `rolling()` for moving averages — never manual loops
- Handle NaN values explicitly — don't let them propagate to signals
- Keep Decimal values at domain boundaries; if Pandas requires numeric conversion, convert only inside bounded indicator calculations and never persist the converted value.

---

## ccxt

### Exchange Setup

```python
import ccxt.async_support as ccxt

# Binance
exchange = ccxt.binance({
    "apiKey": api_key,
    "secret": api_secret,
    "options": {"defaultType": "spot"},
})

# Testnet mode
exchange.set_sandbox_mode(True)
```

### Fetch Candles

```python
async def fetch_candles(symbol: str, timeframe: str, since: int, limit: int):
    candles = await exchange.fetch_ohlcv(symbol, timeframe, since, limit)
    return pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
```

### Place Order

```python
async def place_order(symbol: str, side: str, amount: Decimal):
    order = await exchange.create_order(
        symbol=symbol,
        type="market",
        side=side,
        amount=format_exchange_quantity(amount),
    )
    return order
```

### Rules

- Always use `set_sandbox_mode(True)` for testnet — never skip this
- Always handle `ccxt.NetworkError` and `ccxt.ExchangeError` separately
- Always use async methods (`fetch_ohlcv`, `create_order`) — not sync versions
- Symbol format is exchange-specific (e.g., `"BTC/USDT"` for Binance)
- Never hardcode API keys — always use environment variables
- Never convert money or quantity values to Python `float`; use exchange-specific Decimal formatting at the adapter boundary

---

## httpx

httpx is reserved for future HTTP-based provider or broker adapters. Binance Spot uses ccxt in the MVP.

### Rules

- Always use `httpx.AsyncClient()` — never `requests`
- Always call `response.raise_for_status()` — never ignore HTTP errors
- Always use context managers (`async with`) for client lifecycle
- Never hardcode API keys — always use environment variables

---

## asyncio

Reference skill: `.agents/skills/asyncio/SKILL.md`.

Atlas's worker runs multiple isolated bot pipelines. Async task ownership, cancellation,
failure isolation, and graceful shutdown are part of the architecture, not optional helper
details.

### Rules

- Use `asyncio.run()` only at synchronous process entrypoints.
- Use `asyncio.get_running_loop()` inside running async code; do not use
  `asyncio.get_event_loop()` for new code.
- Keep explicit ownership of tasks created with `asyncio.create_task()` or `asyncio.TaskGroup`.
- Long-running tasks must clean up and re-raise `asyncio.CancelledError`.
- Use `asyncio.gather()` only when its failure behavior is intentional. Independent bot or
  feed operations must not be silently cancelled because an unrelated operation failed.
- Move unavoidable blocking calls to an executor; do not block the worker event loop.

---

## websockets

### Live Data Feed

```python
import websockets
import json

async def subscribe_to_candles(url: str, on_candle):
    async with websockets.connect(url) as ws:
        async for message in ws:
            data = json.loads(message)
            candle = parse_candle(data)
            await on_candle(candle)
```

### Reconnection

```python
async def connect_with_reconnect(url: str, on_message, max_retries: int = 5):
    for attempt in range(max_retries):
        try:
            async with websockets.connect(url) as ws:
                async for message in ws:
                    await on_message(json.loads(message))
        except websockets.ConnectionClosed:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise
```

### Rules

- Always handle `websockets.ConnectionClosed` — connections drop
- Always implement reconnection with exponential backoff
- Always parse JSON messages — never use raw strings
- Always close connections in finally blocks
- Never block the event loop with synchronous operations inside WebSocket handlers

---

## Pydantic and pydantic-settings

Reference skill: `.agents/skills/fastapi/SKILL.md` and its Pydantic reference. Atlas uses
Pydantic v2 APIs throughout new transport and configuration models.

### Configuration

```python
# backend/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://atlas:atlas@localhost:5432/atlas"
    binance_api_key: str = ""
    binance_api_secret: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
```

### Rules

- Always use `BaseSettings` for configuration — never raw `os.getenv`
- Use `model_config`, not the Pydantic v1 `class Config` pattern.
- Use `field_validator` and `model_validator`, not `validator` or `root_validator`.
- Always load from `.env` files — never hardcode secrets
- Always provide sensible defaults for non-critical settings
- Never log or expose API keys
- Use `${VAR_NAME}` syntax in YAML config for environment variable substitution

---

## structlog

### Setup

```python
# backend/core/logging.py
import structlog

def setup_logging():
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
```

### Usage

```python
import structlog

logger = structlog.get_logger()

# Basic logging
logger.info("order_placed", order_id=order.id, instrument=order.instrument)

# With context
logger = logger.bind(component="ExecutionEngine", broker="binance")
logger.error("order_failed", error=str(e), order_id=order.id)

# With exc_info
logger.exception("strategy_error", exc_info=True)
```

### Rules

- Always use structured logging (`logger.info("event_name", key=value)`) — never f-strings
- Always include context (order_id, instrument, etc.) — never log bare messages
- Use `logger.bind()` to attach component context
- Log errors with `logger.exception()` — not `logger.error(str(e))`
- Never log API keys or secrets

---

## pytest

### Test Structure

```python
# tests/test_strategy.py
import pytest
from backend.strategy.base import Strategy
from backend.strategy.examples.sma_crossover import SMACrossoverStrategy

class TestSMACrossoverStrategy:
    def setup_method(self):
        self.strategy = SMACrossoverStrategy({"fast_period": 10, "slow_period": 50})

    def test_buy_signal_on_crossover(self):
        candles = generate_uptrend_candles(100)
        signal = self.strategy.on_candle(candles[-1])
        assert signal is not None
        assert signal.direction == SignalDirection.BUY

    def test_no_signal_insufficient_data(self):
        candles = generate_uptrend_candles(5)
        signal = self.strategy.on_candle(candles[-1])
        assert signal is None
```

### Async Tests

```python
# tests/test_backtest.py
import pytest

@pytest.mark.asyncio
async def test_full_backtest_flow():
    engine = BacktesterEngine(...)
    result = await engine.run(config)
    assert result.status == BacktestStatus.COMPLETED
```

### Rules

- Always use `pytest.mark.asyncio` for async tests
- Always use descriptive test names that explain the scenario
- Always use `setup_method` or fixtures for test setup — never put setup in test methods
- Always assert one thing per test — not multiple assertions testing different things
- Test both success and failure paths
- Never test implementation details — test behavior

---

## Next.js 16

Reference skill: `.agents/skills/nextjs-core/SKILL.md`. Atlas resolves Next.js 16.2.12 with
React and React DOM 19.2.8. The frontend is an operational UI over the FastAPI REST/WebSocket
API; Next.js route handlers and Server Actions must not become a second trading-state API
boundary without an architecture decision.

Next.js 16 requires Node.js 20.9 or newer. The `next lint` command and the Next config `eslint`
option are removed; run the ESLint CLI through the frontend `lint` script instead. Atlas uses
ESLint flat config in `frontend/eslint.config.mjs`. `next build` does not run linting, so lint
and build remain separate checks.

Next.js 16 uses Turbopack by default for `next dev` and `next build`. Atlas has no custom
webpack or Turbopack configuration and does not enable optional React Compiler, Cache Components,
filesystem caching, or other experimental features.

### File-Based Routing

```
app/
├── page.tsx                    # /
├── dashboard/
│   └── page.tsx                # /dashboard
├── strategies/
│   ├── page.tsx                # /strategies
│   └── [id]/
│       └── page.tsx            # /strategies/:id
├── backtests/
│   └── page.tsx                # /backtests
└── api/
    ├── strategies/
    │   └── route.ts            # /api/strategies
    └── health/
        └── route.ts            # /api/health
```

Dynamic page parameters and page search parameters are promises in the Next.js 16 App Router
API. Request-time `cookies()`, `headers()`, and `draftMode()` are asynchronous as well:

```tsx
type StrategyPageProps = {
  params: Promise<{ id: string }>
}

export default async function StrategyPage({ params }: StrategyPageProps) {
  const { id } = await params
  const strategy = await fetchStrategy(id)
  return <StrategyDetails strategy={strategy} />
}
```

Use the same awaited pattern in layouts, route handlers, metadata and image generators, and
sitemaps when those conventions are introduced. Task 1 verified that Atlas currently has no
dynamic routes, metadata/image/sitemap generators, or synchronous request API usage.

### API Routes

```typescript
// Use FastAPI for Atlas trading and persistence endpoints. This pattern is only
// for a frontend-local route handler when one is explicitly required.
// app/api/health/route.ts
import { NextResponse } from "next/server"

export async function GET(): Promise<Response> {
  try {
    return NextResponse.json({ status: "ok" })
  } catch {
    return NextResponse.json({ error: "Unable to read health" }, { status: 503 })
  }
}
```

### Server Components (Default)

```tsx
// app/dashboard/page.tsx
export default async function DashboardPage() {
  const [strategies, account] = await Promise.all([
    fetchStrategies(),
    fetchAccountSummary(),
  ])
  return <Dashboard strategies={strategies} account={account} />
}
```

Use `Suspense` and route-level `loading.tsx` boundaries for slow, independently useful
dashboard sections. Do not broadly cache positions, P&L, bot status, or broker state;
freshness and WebSocket connection state must be explicit. Cache only stable or explicitly
scoped data, and revalidate it narrowly after the owning FastAPI mutation completes.

### Client Components

```tsx
"use client"
import { useState, useEffect } from "react"

export function TradingChart({ data }: { data: CandleData[] }) {
  const [chart, setChart] = useState<IChartApi | null>(null)
  // ... client-side logic
}
```

### Rules

- Server Components are the default — never add `"use client"` unless needed
- Always use `"use client"` for components with hooks, event handlers, or browser APIs
- Always use `NextResponse` for API route responses
- Always handle errors in API routes — return proper status codes
- Never put sensitive data in Client Components — server-side first
- Treat FastAPI as the canonical API for trading commands and durable state.
- Use `params` and `searchParams` according to the verified Next.js version; await promise
  values in the App Router API.
- Add `loading.tsx`, `error.tsx`, and `not-found.tsx` where a route has meaningful loading,
  failure, or missing-resource states.
- Do not use Server Actions as a replacement for FastAPI trading endpoints without updating
  the architecture and security boundary first.
- Keep FastAPI as the canonical API for trading commands, persistence, and durable state; a
  frontend-local route handler is only appropriate for an explicitly local concern such as
  health reporting.
- Next.js 16's `proxy.ts` convention is the successor to `middleware.ts`; Atlas currently has
  neither file nor related configuration. Review the proxy runtime and naming rules before
  introducing request interception.

---

## React 19.2

Next.js 16's App Router is compatible with React 19.2. Atlas resolves React and React DOM
19.2.8. Use React 19.2 APIs only where they solve a concrete UI need; React Compiler,
`useEffectEvent`, View Transitions, and Activity are not enabled or required by the current
application.

### Hooks

```tsx
"use client"
import { useState, useEffect, useCallback } from "react"

export function BotCard({ bot }: { bot: Bot }) {
  const [status, setStatus] = useState(bot.status)

  useEffect(() => {
    setStatus(bot.status)
  }, [bot.status])

  const handleStop = useCallback(async () => {
    await api.post(`/bots/${bot.id}/stop`)
  }, [bot.id])

  return <div>{status}</div>
}
```

### Rules

- Always use hooks in Client Components only
- Always use `useCallback` for event handlers passed as props
- Always use `useMemo` for expensive computations
- Always clean up effects (return cleanup functions)
- Never call hooks conditionally

---

## Shadcn/ui

### Usage

```tsx
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

export function BotCard({ bot }: { bot: Bot }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{bot.name}</CardTitle>
        <Badge variant={bot.status === "running" ? "default" : "secondary"}>
          {bot.status}
        </Badge>
      </CardHeader>
      <CardContent>
        <p>Strategy: {bot.strategy}</p>
        <Button onClick={handleStop}>Stop</Button>
      </CardContent>
    </Card>
  )
}
```

### Rules

- Always import from `@/components/ui/` — never from external packages
- Always use Shadcn components for consistency — never build custom buttons, cards, etc.
- Use `variant` prop for visual states — not custom CSS
- Follow existing component patterns in the codebase

---

## TradingView Lightweight Charts

### Candlestick Chart

```tsx
"use client"
import { useEffect, useRef } from "react"
import { createChart, IChartApi, CandlestickData } from "lightweight-charts"

export function CandlestickChart({ data }: { data: CandlestickData[] }) {
  const chartRef = useRef<HTMLDivElement>(null)
  const chart = useRef<IChartApi>()

  useEffect(() => {
    if (!chartRef.current) return

    chart.current = createChart(chartRef.current, {
      width: 800,
      height: 400,
      layout: {
        background: { color: "#1a1a2e" },
        textColor: "#e0e0e0",
      },
      grid: {
        vertLines: { color: "#2a2a3e" },
        horzLines: { color: "#2a2a3e" },
      },
    })

    const candlestickSeries = chart.current.addCandlestickSeries({
      upColor: "#26a69a",
      downColor: "#ef5350",
      borderVisible: false,
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
    })

    candlestickSeries.setData(data)

    return () => {
      chart.current?.remove()
    }
  }, [data])

  return <div ref={chartRef} />
}
```

### Rules

- Always use `"use client"` — charting requires browser APIs
- Always clean up chart in useEffect return — prevent memory leaks
- Always use dark theme colors for consistency
- Use `setData()` for initial load, `update()` for real-time updates
- Never update chart on every tick — batch updates

---

## TanStack React Query

### Setup

```tsx
// app/providers.tsx
"use client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

const queryClient = new QueryClient()

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}
```

### Usage

```tsx
"use client"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { getStrategies, createStrategy } from "@/lib/api"

export function useStrategies() {
  return useQuery({
    queryKey: ["strategies"],
    queryFn: getStrategies,
  })
}

export function useCreateStrategy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createStrategy,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["strategies"] })
    },
  })
}
```

### Rules

- Always use `queryKey` arrays for cache invalidation
- Always invalidate related queries after mutations
- Always use `useQuery` for data fetching — never raw `fetch` in components
- Always handle loading and error states in components

---

## Axios

### API Client

```typescript
// lib/api.ts
import axios from "axios"

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  headers: {
    "Content-Type": "application/json",
  },
})

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error("API Error:", error.response?.data || error.message)
    return Promise.reject(error)
  }
)

export default api
```

### Usage

```typescript
import api from "@/lib/api"

// GET
const { data } = await api.get("/strategies")

// POST
const { data } = await api.post("/strategies", { name: "sma_crossover", ... })

// PUT
await api.put(`/strategies/${id}`, { parameters: { fast_period: 20 } })

// DELETE
await api.delete(`/strategies/${id}`)
```

### Rules

- Always use the shared `api` instance — never create new instances
- Always handle errors in interceptors or component level
- Always use TypeScript types for request/response data
- Never put API keys in frontend code — only in `.env` files

---

## Sonner

### Usage

```tsx
import { toast } from "sonner"

// Basic notifications
toast.success("Position closed")
toast.error("Order rejected")
toast.warning("Connection lost")

// With description
toast("Bot started", {
  description: "BTC Momentum · 1H · Binance",
})

// Promise-based (for async operations)
toast.promise(saveStrategy(), {
  loading: "Saving strategy...",
  success: "Strategy saved",
  error: "Failed to save strategy",
})
```

### Rules

- Always import from `"sonner"` — never build custom toast components
- Use `toast.success()` for positive outcomes (fills, position opens, saves)
- Use `toast.error()` for failures (rejected orders, connection lost, errors)
- Use `toast()` with description for contextual information
- Never stack multiple toasts for related events — debounce or combine
- Position toasts at bottom-right (default) unless layout requires otherwise

---

## Tailwind CSS

Reference skill: `.agents/skills/tailwind-css/SKILL.md`. Atlas styling tokens and component
patterns are defined in `context/ui-tokens.md` and `context/ui-registry.md`.

### Utility Classes

```tsx
<div className="flex items-center justify-between p-4 border rounded-lg">
  <h2 className="text-lg font-semibold">Dashboard</h2>
  <Badge variant="outline">Live</Badge>
</div>
```

Use the shared `cn()` utility for conditional or conflicting classes:

```tsx
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}
```

Atlas uses Tailwind 4's CSS-first setup. Define project tokens in the existing stylesheet
and use the `atlas-*` utilities documented in `context/ui-tokens.md`; do not introduce a
legacy configuration file unless the dependency setup changes.

### Rules

- Always use utility classes — never write custom CSS unless absolutely necessary
- Always use consistent spacing (p-4, gap-4, etc.)
- Use mobile-first responsive prefixes where the layout needs to adapt; Atlas remains
  desktop-first, so do not sacrifice the operational desktop layout for parity.
- Prefer components, CVA, and token utilities over repeated class strings. Use `@apply` only
  when it is justified by the existing Tailwind 4 stylesheet architecture.
- Follow existing color patterns in the codebase
- Never use color alone for trading status; pair semantic colors with text or iconography.
