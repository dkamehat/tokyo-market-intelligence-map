"""Tests for the MLIT ingestion CLI layer (no network/GIS)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ingest_mlit_accessibility.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("ingest_mlit_accessibility", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


script = _load_script()


def test_resolve_mode_auto_defaults_to_sample() -> None:
    assert script.resolve_mode("auto") == "sample"


def test_resolve_mode_respects_explicit_choice() -> None:
    assert script.resolve_mode("sample") == "sample"
    assert script.resolve_mode("live") == "live"


def test_live_mode_stops_with_gis_proposal() -> None:
    # Live ward assignment is deferred -> exit code 3, no crash.
    assert script.main(["--mode", "live"]) == 3


def test_load_population_missing_file_returns_none(tmp_path: Path) -> None:
    assert script.load_population(tmp_path / "nope.csv") is None
