import os
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config

_ROOT = Path(__file__).parents[2]


def _test_database_url() -> str | None:
    """Return the configured integration URL when it names a test database."""
    url = os.environ.get("ATLAS_TEST_DATABASE_URL")
    if not url:
        return None
    database = urlparse(url).path.rsplit("/", 1)[-1]
    if not database.endswith("_test"):
        return None
    return url


def _ensure_schema_at_head() -> None:
    url = _test_database_url()
    if not url:
        return
    config = Config(str(_ROOT / "alembic.ini"))
    config.set_main_option("script_location", "backend/persistence/migrations")
    # Migration tests intentionally exercise teardown states.  Restore the
    # schema immediately before a root-level integration test can use it.
    os.environ["ATLAS_DATABASE_URL"] = url
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    from backend.config import get_settings

    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def ensure_root_integration_schema(request: pytest.FixtureRequest) -> None:
    """Keep root-level integration tests independent of migration teardown."""
    if request.node.get_closest_marker("integration") is None:
        return
    node_path = cast(Path, request.node.path)
    if node_path.parent != Path(__file__).parent:
        return
    _ensure_schema_at_head()
