"""Tests for the daytime ingest CLI layer (no network)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ingest_estat_daytime.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("ingest_estat_daytime", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


script = _load_script()


def test_resolve_mode_without_appid_is_sample(monkeypatch) -> None:
    monkeypatch.delenv("ESTAT_APP_ID", raising=False)
    assert script.resolve_mode("auto") == "sample"


def test_resolve_mode_respects_explicit_choice() -> None:
    assert script.resolve_mode("sample") == "sample"
    assert script.resolve_mode("live") == "live"


def test_parse_cat_filters_roundtrip() -> None:
    assert script.parse_cat_filters(["@cat01=01", "@cat02=000"]) == {
        "@cat01": "01",
        "@cat02": "000",
    }


def test_live_default_filter_targets_daytime_total() -> None:
    # Live mode must default to the verified daytime (昼間人口) cell, NOT the sample codes,
    # so a forgotten --cat-filter cannot silently mis-query the live table.
    assert script.DEFAULT_LIVE_FILTER == {"@cat01": "180"}
    assert script.default_filter_for_mode("live") == {"@cat01": "180"}


def test_sample_default_filter_matches_fixture() -> None:
    # Sample mode keeps the fixture's illustrative codes (behaviour unchanged).
    assert script.DEFAULT_SAMPLE_FILTER == {"@cat01": "01", "@cat02": "000"}
    assert script.default_filter_for_mode("sample") == {"@cat01": "01", "@cat02": "000"}


def test_sample_default_filter_selects_rows_from_fixture() -> None:
    # The sample default filter actually resolves to one row per ward in the fixture.
    import json
    from pathlib import Path

    from tokyo_market_intel.ingestion.estat_daytime import build_daytime_layer

    fixture = Path(__file__).resolve().parents[1] / "data" / "sample" / "estat_daytime_sample.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    layer = build_daytime_layer(payload, value_filter=script.DEFAULT_SAMPLE_FILTER)
    assert len(layer) == 6  # 6 Tokyo wards in the fixture (Yokohama filtered out)


def test_load_resident_population_handles_missing(tmp_path: Path) -> None:
    assert script.load_resident_population(tmp_path / "nope.csv") is None
