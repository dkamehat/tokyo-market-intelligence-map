"""Unit tests for the MLIT cost-pressure (land price) transform (no network/GIS)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tokyo_market_intel.ingestion.mlit_cost import (
    aggregate_cost_by_ward,
    build_cost_layer,
    classify_cost_layer,
)
from tokyo_market_intel.ingestion.provenance import SOURCE_MODE_LIVE, SOURCE_MODE_SAMPLE
from tokyo_market_intel.sources.mlit_cost import L01_ATTRIBUTION, parse_land_price_features

_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "sample"
SAMPLE_PATH = _DATA_DIR / "mlit_landprice_sample.json"


@pytest.fixture
def records() -> list[dict]:
    geojson = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    return parse_land_price_features(geojson)


def test_parse_reads_code_and_price(records: list[dict]) -> None:
    assert len(records) == 12
    chiyoda = [r for r in records if r["area_code"] == "13101"]
    assert {"4000000", "6000000", "5000000", "-"} == {r["price"] for r in chiyoda}


def test_aggregate_median_mean_count_and_filters(records: list[dict]) -> None:
    agg = aggregate_cost_by_ward(records)
    by_code = agg.set_index("area_code")

    # Chiyoda: 3 valid prices (the "-" dropped) -> median/mean 5,000,000.
    assert by_code.loc["13101", "observation_count"] == 3
    assert by_code.loc["13101", "land_price_median"] == pytest.approx(5_000_000)
    assert by_code.loc["13101", "land_price_mean"] == pytest.approx(5_000_000)
    # Shibuya: [3M, 3M, 9M] -> median 3M, mean 5M.
    assert by_code.loc["13113", "land_price_median"] == pytest.approx(3_000_000)
    assert by_code.loc["13113", "land_price_mean"] == pytest.approx(5_000_000)
    # Nakano: single observation.
    assert by_code.loc["13114", "observation_count"] == 1
    # Non-ward (14100) filtered; no-code record dropped.
    assert "14100" not in by_code.index


def test_build_cost_layer_sample_is_not_real(records: list[dict]) -> None:
    layer = build_cost_layer(records)  # default sample
    assert list(layer.columns) == [
        "area",
        "area_code",
        "land_price_median",
        "cost_pressure_score",
        "land_price_mean",
        "observation_count",
        "source_mode",
        "data_basis",
        "attribution",
    ]
    assert (layer["source_mode"] == SOURCE_MODE_SAMPLE).all()
    assert not layer["data_basis"].str.startswith("public:").any()
    assert (layer["attribution"] == L01_ATTRIBUTION).all()
    assert classify_cost_layer(layer) == "sample_fixture"

    # Highest median land price -> highest cost pressure, ranked first.
    assert layer.iloc[0]["area"] == "Chiyoda"
    assert layer["cost_pressure_score"].max() == pytest.approx(100.0)
    assert layer["cost_pressure_score"].min() == pytest.approx(0.0)
    assert layer["cost_pressure_score"].is_monotonic_decreasing


def test_build_cost_layer_live_is_public(records: list[dict]) -> None:
    layer = build_cost_layer(records, source_mode=SOURCE_MODE_LIVE)
    assert (layer["source_mode"] == SOURCE_MODE_LIVE).all()
    assert layer["data_basis"].str.startswith("public:MLIT").all()
    assert classify_cost_layer(layer) == "live_public"


def test_non_numeric_and_missing_prices_dropped() -> None:
    records = [
        {"area_code": "13101", "price": "5000000"},
        {"area_code": "13101", "price": "X"},      # non-numeric -> dropped
        {"area_code": "13104", "price": None},      # missing -> dropped
    ]
    agg = aggregate_cost_by_ward(records)
    by_code = agg.set_index("area_code")
    assert by_code.loc["13101", "observation_count"] == 1
    assert "13104" not in by_code.index


def test_build_rejects_unknown_source_mode(records: list[dict]) -> None:
    with pytest.raises(ValueError, match="source_mode"):
        build_cost_layer(records, source_mode="totally-real")


def test_classify_missing_and_unknown() -> None:
    assert classify_cost_layer(None) == "missing"
    assert classify_cost_layer(pd.DataFrame()) == "missing"
    no_mode = pd.DataFrame({"area": ["Chiyoda"], "land_price_median": [5_000_000]})
    assert classify_cost_layer(no_mode) == "unknown"
