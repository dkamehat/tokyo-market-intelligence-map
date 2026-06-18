"""Tests for the OSM ingestion CLI layer (no network)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ingest_osm_competition.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("ingest_osm_competition", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


script = _load_script()


def test_resolve_mode_auto_defaults_to_sample() -> None:
    # Overpass needs no credential; auto must never silently hit the network.
    assert script.resolve_mode("auto") == "sample"


def test_resolve_mode_respects_explicit_choice() -> None:
    assert script.resolve_mode("sample") == "sample"
    assert script.resolve_mode("live") == "live"


def test_load_population_missing_file_returns_none(tmp_path: Path) -> None:
    assert script.load_population(tmp_path / "nope.csv") is None


def test_load_population_reads_population_map(tmp_path: Path) -> None:
    csv = tmp_path / "demand.csv"
    csv.write_text("area_code,population\n13104,349385\n13101,66680\n", encoding="utf-8")
    population = script.load_population(csv)
    assert population == {"13104": 349385, "13101": 66680}
