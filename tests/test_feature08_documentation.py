from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_feature08_documents_current_usdm_routes_and_registry_boundary() -> None:
    document = (ROOT / "context/features/08-live-data-streaming.md").read_text()

    assert "/public/ws/" in document
    assert "/market/ws/" in document
    assert "LiveProviderRegistry" in document
    assert "optional live-market-context capability" in document
    assert "Feature 09 owns mode-specific pipeline assembly" in document
    assert "Feature 12" in document


def test_feature08_documents_deferred_execution_and_coin_m_scope() -> None:
    document = (ROOT / "context/features/08-live-data-streaming.md").read_text()

    assert "authenticated execution" in document
    assert "COIN-M" in document
    assert "PaperBroker integration" in document
    assert "historical Spot" in document
