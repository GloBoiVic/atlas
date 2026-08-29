"""Explicitly opt-in, isolated E2E lifecycle diagnostic application factory."""

from __future__ import annotations

import json
import os
from urllib.parse import urlparse

from backend.api.app import create_app as create_production_app
from backend.experiments.lifecycle import ExperimentLifecycleDiagnostic


def _test_database(url: str) -> bool:
    return urlparse(url).path.rsplit("/", 1)[-1].endswith("_test")


def _stdout_sink(record: ExperimentLifecycleDiagnostic) -> None:
    print(
        "ATLAS_E2E_LIFECYCLE "
        + json.dumps(record.as_dict(), sort_keys=True, separators=(",", ":")),
        flush=True,
    )


def create_app():
    database_url = os.environ.get("ATLAS_E2E_DATABASE_URL") or os.environ.get(
        "ATLAS_DATABASE_URL", ""
    )
    lifecycle = os.environ.get("ATLAS_E2E_LIFECYCLE_DIAGNOSTIC") == "1"
    if not lifecycle:
        return create_production_app()
    if not database_url or not _test_database(database_url):
        raise RuntimeError("E2E lifecycle diagnostics require a *_test database")
    return create_production_app(
        lifecycle_diagnostic_sink=_stdout_sink if lifecycle else None,
    )
