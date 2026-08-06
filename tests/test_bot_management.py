from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.api.bot_schemas import BotReadResponse
from backend.bot.service import BotConflict, BotNotFound, BotService, BotValidationError
from backend.core.account_mode import AccountMode
from backend.core.clock import Clock
from backend.core.events import EventBus
from backend.persistence.repositories.memory import InMemorySupervisorRepositories
from backend.persistence.repositories.protocols import StrategyVersionRecord
from backend.strategy.base import Strategy
from backend.strategy.registry import StrategyRegistry


class FixedClock(Clock):
    def now(self) -> datetime:
        return datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


class EmptyStrategy(Strategy):
    def on_candle(self, candle: object) -> None:
        return None


class FakeSupervisor:
    def __init__(self, repository: InMemorySupervisorRepositories) -> None:
        self.repository = repository
        self.calls: list[tuple[str, object]] = []

    async def start(self, bot_id: object) -> bool:
        self.calls.append(("start", bot_id))
        return True

    async def stop(self, bot_id: object) -> bool:
        self.calls.append(("stop", bot_id))
        return True

    async def pause(self, bot_id: object) -> bool:
        self.calls.append(("pause", bot_id))
        return True

    async def restore(self, bot_id: object) -> bool:
        self.calls.append(("restore", bot_id))
        return True


def make_service() -> tuple[BotService, InMemorySupervisorRepositories, FakeSupervisor]:
    account_id = uuid4()
    repository = InMemorySupervisorRepositories(account_modes={account_id: "paper"})
    version_id = uuid4()
    strategy_repository = _StrategyRepository(
        StrategyVersionRecord(version_id, "empty", "1.0.0", "a" * 40)
    )
    registry = StrategyRegistry()
    registry.register(version_id, "empty", "a" * 40, EmptyStrategy)
    supervisor = FakeSupervisor(repository)
    service = BotService(
        event_bus=EventBus(),
        supervisor=supervisor,  # type: ignore[arg-type]
        repository=repository,
        strategy_repository=strategy_repository,
        strategy_registry=registry,
        clock=FixedClock(),
    )
    return service, repository, supervisor


class _StrategyRepository:
    def __init__(self, version: StrategyVersionRecord) -> None:
        self.version = version

    async def get(self, strategy_version_id: object) -> StrategyVersionRecord | None:
        return self.version if strategy_version_id == self.version.id else None


@pytest.mark.asyncio
async def test_create_persists_stopped_bot_with_decimal_safe_config() -> None:
    service, repository, _ = make_service()
    account_id = next(iter(repository._account_modes))
    version_id = uuid4()
    # The helper's registry/version is intentionally used for the actual create below.
    version_id = service.strategy_repository.version.id  # type: ignore[attr-defined]

    bot = await service.create_bot(
        name="paper bot",
        strategy_version_id=version_id,
        account_id=account_id,
        broker="binance_usdm",
        mode=AccountMode.PAPER,
        instrument="BTCUSDT",
        timeframe="1m",
        config={"threshold": "1.25"},
    )

    assert bot.status == "stopped"
    assert bot.desired_status == "stopped"
    assert bot.config == {"threshold": "1.25"}
    assert (await repository.get(bot.id)) == bot


@pytest.mark.asyncio
async def test_repeated_identical_create_returns_the_existing_bot() -> None:
    service, repository, _ = make_service()
    account_id = next(iter(repository._account_modes))
    version_id = service.strategy_repository.version.id  # type: ignore[attr-defined]
    request = {
        "name": "paper bot",
        "strategy_version_id": version_id,
        "account_id": account_id,
        "broker": "binance_usdm",
        "mode": AccountMode.PAPER,
        "instrument": "BTCUSDT",
        "timeframe": "1m",
        "config": {"threshold": "1.25"},
    }

    first = await service.create_bot(**request)
    second = await service.create_bot(**request)

    assert second.id == first.id
    assert len(await repository.list(account_id=account_id, mode="paper")) == 1


@pytest.mark.asyncio
async def test_equivalent_numeric_config_values_share_the_identity() -> None:
    service, repository, _ = make_service()
    account_id = next(iter(repository._account_modes))
    version_id = service.strategy_repository.version.id  # type: ignore[attr-defined]
    common = {
        "name": "paper bot",
        "strategy_version_id": version_id,
        "account_id": account_id,
        "broker": "binance_usdm",
        "mode": AccountMode.PAPER,
        "instrument": "BTCUSDT",
        "timeframe": "1m",
    }

    first = await service.create_bot(config={"threshold": 1}, **common)
    second = await service.create_bot(config={"threshold": 1.0}, **common)
    third = await service.create_bot(config={"threshold": Decimal("1.00")}, **common)

    assert second.id == first.id
    assert third.id == first.id
    assert len(await repository.list(account_id=account_id, mode="paper")) == 1


@pytest.mark.asyncio
async def test_numeric_config_and_intentional_string_remain_distinct() -> None:
    service, repository, _ = make_service()
    account_id = next(iter(repository._account_modes))
    version_id = service.strategy_repository.version.id  # type: ignore[attr-defined]
    common = {
        "name": "paper bot",
        "strategy_version_id": version_id,
        "account_id": account_id,
        "broker": "binance_usdm",
        "mode": AccountMode.PAPER,
        "instrument": "BTCUSDT",
        "timeframe": "1m",
    }

    numeric = await service.create_bot(config={"threshold": 1}, **common)
    textual = await service.create_bot(config={"threshold": "1"}, **common)

    assert textual.id != numeric.id
    assert len(await repository.list(account_id=account_id, mode="paper")) == 2


@pytest.mark.asyncio
async def test_update_collision_is_a_conflict_and_preserves_both_bots() -> None:
    service, repository, _ = make_service()
    account_id = next(iter(repository._account_modes))
    version_id = service.strategy_repository.version.id  # type: ignore[attr-defined]
    common = {
        "strategy_version_id": version_id,
        "account_id": account_id,
        "broker": "binance_usdm",
        "mode": AccountMode.PAPER,
        "instrument": "BTCUSDT",
        "timeframe": "1m",
    }
    first = await service.create_bot(name="first", config={"threshold": 1}, **common)
    second = await service.create_bot(name="second", config={"threshold": 1}, **common)

    with pytest.raises(BotConflict, match="already owns"):
        await service.update_bot(second.id, name=first.name)

    persisted_second = await repository.get(second.id)
    assert persisted_second is not None
    assert persisted_second.name == "second"


@pytest.mark.asyncio
async def test_update_stopped_bot_allows_a_distinct_identity() -> None:
    service, _, _ = make_service()
    account_id = next(iter(service.repository._account_modes))  # type: ignore[attr-defined]
    version_id = service.strategy_repository.version.id  # type: ignore[attr-defined]
    bot = await service.create_bot(
        name="paper bot",
        strategy_version_id=version_id,
        account_id=account_id,
        broker="binance_usdm",
        mode=AccountMode.PAPER,
        instrument="BTCUSDT",
        timeframe="1m",
        config={"threshold": 1},
    )

    updated = await service.update_bot(bot.id, config={"threshold": 2})

    assert updated.id == bot.id
    assert updated.config == {"threshold": 2}


@pytest.mark.asyncio
async def test_distinct_create_configuration_gets_a_distinct_bot() -> None:
    service, repository, _ = make_service()
    account_id = next(iter(repository._account_modes))
    version_id = service.strategy_repository.version.id  # type: ignore[attr-defined]
    common = {
        "strategy_version_id": version_id,
        "account_id": account_id,
        "broker": "binance_usdm",
        "mode": AccountMode.PAPER,
        "instrument": "BTCUSDT",
        "timeframe": "1m",
    }

    first = await service.create_bot(name="paper bot", config={"threshold": "1.25"}, **common)
    second = await service.create_bot(name="paper bot", config={"threshold": "1.50"}, **common)

    assert second.id != first.id
    assert len(await repository.list(account_id=account_id, mode="paper")) == 2


@pytest.mark.asyncio
async def test_create_rejects_account_mode_mismatch_and_never_delegates() -> None:
    service, repository, supervisor = make_service()
    account_id = next(iter(repository._account_modes))
    version_id = service.strategy_repository.version.id  # type: ignore[attr-defined]

    with pytest.raises(BotValidationError, match="mode"):
        await service.create_bot(
            name="testnet bot",
            strategy_version_id=version_id,
            account_id=account_id,
            broker="binance_usdm",
            mode=AccountMode.TESTNET,
            instrument="BTCUSDT",
            timeframe="1m",
            config={},
        )

    assert supervisor.calls == []


@pytest.mark.asyncio
async def test_lifecycle_commands_are_scoped_and_delegate_to_supervisor() -> None:
    service, _, supervisor = make_service()
    account_id = next(iter(service.repository._account_modes))  # type: ignore[attr-defined]
    version_id = service.strategy_repository.version.id  # type: ignore[attr-defined]
    bot = await service.create_bot(
        name="paper bot",
        strategy_version_id=version_id,
        account_id=account_id,
        broker="binance_usdm",
        mode=AccountMode.PAPER,
        instrument="BTCUSDT",
        timeframe="1m",
        config={},
    )

    with pytest.raises(BotNotFound):
        await service.start_bot(bot.id, account_id=uuid4(), mode=AccountMode.PAPER)
    await service.stop_bot(bot.id, account_id=account_id, mode=AccountMode.PAPER)
    await service.pause_bot(bot.id, account_id=account_id, mode=AccountMode.PAPER)
    await service.resume_bot(bot.id, account_id=account_id, mode=AccountMode.PAPER)

    assert [call[0] for call in supervisor.calls] == ["stop", "pause", "restore"]


def test_bot_response_preserves_uuid_decimal_and_utc_transport() -> None:
    response = BotReadResponse(
        id=uuid4(),
        name="paper bot",
        strategy_version_id=uuid4(),
        account_id=uuid4(),
        broker="binance_usdm",
        mode=AccountMode.PAPER,
        instrument="BTCUSDT",
        timeframe="1m",
        config={},
        desired_status="running",
        status="starting",
        pnl="1.2300",
        started_at=datetime(2026, 8, 5, tzinfo=UTC),
        stopped_at=None,
        last_error=None,
        created_at=datetime(2026, 8, 5, tzinfo=UTC),
        updated_at=datetime(2026, 8, 5, tzinfo=UTC),
    )
    assert isinstance(response.id, type(uuid4()))
    assert response.pnl == "1.2300"
    assert response.started_at is not None and response.started_at.tzinfo is UTC
