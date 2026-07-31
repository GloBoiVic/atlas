# Library Docs

Project-specific usage patterns for every third-party library in Atlas. This file only covers how we use each library in this specific project — rules, patterns, and constraints specific to Atlas.

Read the relevant section before implementing any feature that touches these libraries.

---

## Before Using Any Library

Before implementing any feature that uses a third party library:

1. **Read this file** for project-specific patterns that override general library knowledge.

2. **Check the architecture context file** for how the component fits into the system.

3. **Check the feature file** for acceptance criteria and technical details.

The order of authority is:

```
This file (project rules) → Architecture file → Feature file → General training knowledge
```

Never rely on general training knowledge alone for library APIs — they change frequently and training data may be outdated.

---

## FastAPI

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
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/strategies", tags=["strategies"])

@router.get("/")
async def list_strategies(service: StrategyService = Depends(get_strategy_service)):
    return await service.list_active()

@router.post("/")
async def create_strategy(
    config: StrategyCreate,
    service: StrategyService = Depends(get_strategy_service),
):
    return await service.register(config)
```

Routes remain thin. Services own business logic and repositories own database access.

### Dependency Injection

```python
# backend/api/deps.py
from backend.persistence.database import async_session

async def get_session():
    async with async_session() as session:
        yield session
```

### WebSocket

```python
# backend/api/websocket.py
from fastapi import WebSocket, WebSocketDisconnect

class ConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        self.connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
```

### Rules

- Always use `Depends(get_session)` for database sessions — never create sessions directly in routes
- Always use `APIRouter` for route groups — never add routes directly to `app`
- Always handle errors gracefully — return proper HTTP status codes
- Always use Pydantic models for request/response validation
- Routes are thin — business logic goes in services, not routes
- Never put trading logic in routes

---

## SQLAlchemy

### Base Model

```python
# backend/persistence/models.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
```

### Model Example

```python
# backend/persistence/models.py
from sqlalchemy import Column, String, Boolean, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

class Strategy(Base, TimestampMixin):
    __tablename__ = "strategies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    entrypoint = Column(String(500), nullable=False)
    repository = Column(String(500), nullable=False)
    version = Column(String(50), nullable=False, default="1.0.0")
    commit_sha = Column(String(64), nullable=False)
    parameters = Column(JSON, nullable=False, default=dict)
    is_active = Column(Boolean, default=True)
```

### Async Session

```python
# backend/persistence/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)
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
    select(Strategy).where(Strategy.is_active == True).order_by(Strategy.created_at.desc())
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

## pydantic-settings

### Configuration

```python
# backend/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://atlas:atlas@localhost:5432/atlas"
    binance_api_key: str = ""
    binance_api_secret: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

### Rules

- Always use `BaseSettings` for configuration — never raw `os.getenv`
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

### API Routes

```typescript
// app/api/strategies/route.ts
import { NextResponse } from "next/server"

export async function GET() {
  const strategies = await fetchStrategies()
  return NextResponse.json(strategies)
}

export async function POST(request: Request) {
  const body = await request.json()
  const strategy = await createStrategy(body)
  return NextResponse.json(strategy, { status: 201 })
}
```

### Server Components (Default)

```tsx
// app/dashboard/page.tsx
export default async function DashboardPage() {
  const data = await fetchStrategies() // Server-side fetch
  return <Dashboard data={data} />
}
```

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

---

## React 19

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

### Utility Classes

```tsx
<div className="flex items-center justify-between p-4 border rounded-lg">
  <h2 className="text-lg font-semibold">Dashboard</h2>
  <Badge variant="outline">Live</Badge>
</div>
```

### Rules

- Always use utility classes — never write custom CSS unless absolutely necessary
- Always use consistent spacing (p-4, gap-4, etc.)
- Always use responsive prefixes for mobile support (md:, lg:)
- Never use `@apply` — it defeats the purpose of Tailwind
- Follow existing color patterns in the codebase
