import pytest


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    from backend.config import get_settings

    get_settings.cache_clear()
