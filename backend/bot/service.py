"""Persisted bot CRUD and supervisor-delegating lifecycle commands."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from backend.core.account_mode import AccountMode
from backend.persistence.repositories.protocols import (
    BotIdentityConflictError,
    BotRecord,
    BotRepository,
    StrategyVersionRepository,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.core.clock import Clock
    from backend.core.events import EventBus
    from backend.strategy.registry import StrategyRegistry
    from backend.worker.supervisor import BotSupervisor

SUPPORTED_TIMEFRAMES = frozenset({"1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"})
_FORBIDDEN_CONFIG_KEYS = frozenset(
    {"import", "import_path", "module", "entrypoint", "api_key", "api_secret", "secret"}
)


class BotError(RuntimeError):
    """Base application error for bot operations."""


class BotNotFound(BotError):
    """The requested bot does not exist."""


class BotValidationError(BotError):
    """The bot configuration is not safe or internally consistent."""


class BotConflict(BotError):
    """The requested configuration or lifecycle operation conflicts with state."""


class BotSafetyError(BotError):
    """A lifecycle operation could not establish safe execution."""


def _json_config(value: Any, path: str = "config") -> object:
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise BotValidationError(f"{path} must be finite")
        return str(value)
    if isinstance(value, dict):
        result: dict[str, object] = {}
        for key, nested in value.items():
            if str(key).lower() in _FORBIDDEN_CONFIG_KEYS:
                raise BotValidationError(f"configuration field {key!r} is not accepted")
            result[str(key)] = _json_config(nested, f"{path}.{key}")
        return result
    if isinstance(value, list):
        return [_json_config(item, f"{path}[]") for item in value]
    if value is None or isinstance(value, (str, int, bool, float)):
        return value
    raise BotValidationError(f"{path} contains a value that is not JSON-compatible")


def _canonical_number(value: Decimal | int | float, path: str) -> dict[str, str]:
    try:
        decimal_value = Decimal(str(value))
    except (TypeError, ValueError) as error:
        raise BotValidationError(f"{path} must be a valid number") from error
    if not decimal_value.is_finite():
        raise BotValidationError(f"{path} must be finite")
    text = format(decimal_value.normalize(), "f")
    return {"__atlas_numeric__": "0" if text in {"", "-0"} else text}


def _canonical_identity(value: Any, path: str = "config") -> object:
    """Encode numeric values by exact Decimal text without changing runtime config types."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (Decimal, int, float)):
        return _canonical_number(value, path)
    if isinstance(value, dict):
        return {
            str(key): _canonical_identity(nested, f"{path}.{key}")
            for key, nested in value.items()
        }
    if isinstance(value, list):
        return [_canonical_identity(item, f"{path}[]") for item in value]
    if value is None or isinstance(value, str):
        return value
    raise BotValidationError(f"{path} contains a value that is not JSON-compatible")


class BotService:
    """Compose persistence, trusted strategies, and the existing supervisor.

    This service deliberately has no lifecycle state machine.  ``BotSupervisor`` owns all
    transitions, reconciliation, pipeline construction, and execution gating.
    """

    def __init__(
        self,
        *,
        event_bus: EventBus,
        supervisor: BotSupervisor,
        repository: BotRepository,
        strategy_repository: StrategyVersionRepository,
        strategy_registry: StrategyRegistry,
        clock: Clock,
    ) -> None:
        self.event_bus = event_bus
        self.supervisor = supervisor
        self.repository = repository
        self.strategy_repository = strategy_repository
        self.strategy_registry = strategy_registry
        self.clock = clock

    async def create_bot(
        self,
        *,
        name: str,
        strategy_version_id: UUID,
        account_id: UUID,
        broker: str,
        mode: AccountMode,
        instrument: str,
        timeframe: str,
        config: Mapping[str, Any],
    ) -> BotRecord:
        """Validate and persist a stopped bot without starting execution."""
        normalized = await self._validate_configuration(
            strategy_version_id,
            account_id,
            broker,
            mode,
            instrument,
            timeframe,
            config,
        )
        identity = _canonical_identity(dict(config))
        if not isinstance(identity, dict):
            raise BotValidationError("config must be an object")
        now = self.clock.now()
        bot = BotRecord(
            id=uuid4(),
            name=name.strip(),
            account_id=account_id,
            broker=broker,
            mode=mode.value,
            instrument=instrument,
            timeframe=timeframe,
            desired_status="stopped",
            status="stopped",
            last_error=None,
            started_at=None,
            stopped_at=now,
            strategy_version_id=strategy_version_id,
            config=normalized,
            config_identity=identity,
            created_at=now,
            updated_at=now,
        )
        return await self.repository.create(bot)

    async def get_bot(
        self,
        bot_id: UUID,
        *,
        account_id: UUID | None = None,
        mode: AccountMode | None = None,
    ) -> BotRecord:
        bot = await self.repository.get(bot_id)
        if bot is None:
            raise BotNotFound(f"bot {bot_id} was not found")
        self._check_scope(bot, account_id, mode)
        return bot

    async def list_bots(
        self, *, account_id: UUID | None = None, mode: AccountMode | None = None
    ) -> list[BotRecord]:
        return await self.repository.list(
            account_id=account_id,
            mode=mode.value if mode is not None else None,
        )

    async def update_bot(self, bot_id: UUID, **changes: Any) -> BotRecord:
        bot = await self.get_bot(bot_id)
        if bot.status != "stopped" or bot.desired_status != "stopped":
            raise BotConflict("stop the bot before changing its configuration")
        values = {
            "name": changes.get("name", bot.name),
            "strategy_version_id": changes.get("strategy_version_id", bot.strategy_version_id),
            "account_id": changes.get("account_id", bot.account_id),
            "broker": changes.get("broker", bot.broker),
            "mode": changes.get("mode", AccountMode(bot.mode)),
            "instrument": changes.get("instrument", bot.instrument),
            "timeframe": changes.get("timeframe", bot.timeframe),
            "config": changes.get("config", bot.config),
        }
        if not isinstance(values["mode"], AccountMode):
            values["mode"] = AccountMode(values["mode"])
        normalized = await self._validate_configuration(
            values["strategy_version_id"],
            values["account_id"],
            values["broker"],
            values["mode"],
            values["instrument"],
            values["timeframe"],
            values["config"],
        )
        identity = _canonical_identity(values["config"])
        if not isinstance(identity, dict):
            raise BotValidationError("config must be an object")
        updated = BotRecord(
            id=bot.id,
            name=str(values["name"]).strip(),
            account_id=values["account_id"],
            broker=str(values["broker"]),
            mode=values["mode"].value,
            instrument=str(values["instrument"]),
            timeframe=str(values["timeframe"]),
            desired_status=bot.desired_status,
            status=bot.status,
            last_error=bot.last_error,
            started_at=bot.started_at,
            stopped_at=bot.stopped_at,
            strategy_version_id=values["strategy_version_id"],
            config=normalized,
            config_identity=identity,
            pnl=bot.pnl,
            created_at=bot.created_at,
            updated_at=self.clock.now(),
        )
        try:
            result = await self.repository.update_configuration(bot_id, updated)
        except BotIdentityConflictError as error:
            raise BotConflict("another bot already owns this configuration") from error
        if result is None:
            raise BotNotFound(f"bot {bot_id} was not found")
        return result

    async def start_bot(
        self,
        bot_id: UUID,
        *,
        account_id: UUID | None = None,
        mode: AccountMode | None = None,
    ) -> BotRecord:
        bot = await self.get_bot(bot_id, account_id=account_id, mode=mode)
        await self._validate_existing(bot)
        if bot.status == "running" and bot.desired_status == "running":
            return bot
        await self.supervisor.start(bot_id)
        return await self.get_bot(bot_id, account_id=account_id, mode=mode)

    async def stop_bot(
        self,
        bot_id: UUID,
        *,
        account_id: UUID | None = None,
        mode: AccountMode | None = None,
    ) -> BotRecord:
        await self.get_bot(bot_id, account_id=account_id, mode=mode)
        await self.supervisor.stop(bot_id)
        return await self.get_bot(bot_id, account_id=account_id, mode=mode)

    async def pause_bot(
        self,
        bot_id: UUID,
        *,
        account_id: UUID | None = None,
        mode: AccountMode | None = None,
    ) -> BotRecord:
        await self.get_bot(bot_id, account_id=account_id, mode=mode)
        await self.supervisor.pause(bot_id)
        return await self.get_bot(bot_id, account_id=account_id, mode=mode)

    async def resume_bot(
        self,
        bot_id: UUID,
        *,
        account_id: UUID | None = None,
        mode: AccountMode | None = None,
    ) -> BotRecord:
        bot = await self.get_bot(bot_id, account_id=account_id, mode=mode)
        await self._validate_existing(bot)
        await self.supervisor.restore(bot_id)
        return await self.get_bot(bot_id, account_id=account_id, mode=mode)

    async def _validate_existing(self, bot: BotRecord) -> None:
        if bot.mode == AccountMode.PRODUCTION.value:
            raise BotValidationError("production mode is reserved and rejected")
        if bot.strategy_version_id is None:
            raise BotValidationError("bot has no pinned strategy version")
        await self._validate_configuration(
            bot.strategy_version_id,
            bot.account_id,
            bot.broker,
            AccountMode(bot.mode),
            bot.instrument,
            bot.timeframe,
            bot.config,
        )

    async def _validate_configuration(
        self,
        strategy_version_id: UUID,
        account_id: UUID,
        broker: str,
        mode: AccountMode,
        instrument: str,
        timeframe: str,
        config: Mapping[str, Any],
    ) -> dict[str, object]:
        if mode is AccountMode.PRODUCTION:
            raise BotValidationError("production mode is reserved and rejected")
        account_mode = await self.repository.get_account_mode(account_id)
        if account_mode is None:
            raise BotValidationError("account does not exist")
        if account_mode != mode.value:
            raise BotValidationError("bot mode does not match account mode")
        if not broker.strip():
            raise BotValidationError("broker is required")
        if not instrument or len(instrument) > 50 or instrument != instrument.upper():
            raise BotValidationError("instrument must be a normalized uppercase symbol")
        if timeframe not in SUPPORTED_TIMEFRAMES:
            raise BotValidationError("unsupported timeframe")
        version = await self.strategy_repository.get(strategy_version_id)
        if version is None:
            raise BotValidationError("strategy version is unavailable")
        prepared_value = _json_config(dict(config))
        prepared = prepared_value if isinstance(prepared_value, dict) else None
        if not isinstance(prepared, dict):
            raise BotValidationError("config must be an object")
        try:
            self.strategy_registry.resolve(
                strategy_version_id,
                version.name,
                version.commit_sha,
                dict(prepared),
            )
        except Exception as error:
            raise BotValidationError(
                f"strategy identity or configuration is unsafe: {error}"
            ) from error
        return prepared

    @staticmethod
    def _check_scope(bot: BotRecord, account_id: UUID | None, mode: AccountMode | None) -> None:
        if account_id is not None and bot.account_id != account_id:
            raise BotNotFound("bot is outside the requested account scope")
        if mode is not None and bot.mode != mode.value:
            raise BotNotFound("bot is outside the requested mode scope")
