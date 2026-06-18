"""Unit tests for the MLIT accessibility transform and provenance (no network/GIS)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tokyo_market_intel.ingestion.mlit_accessibility import (
    build_accessibility_layer,
    classify_accessibility_layer,
    count_stations_by_ward,
)
from tokyo_market_intel.ingestion.provenance import SOURCE_MODE_LIVE, SOURCE_MODE_SAMPLE
from tokyo_market_intel.sources.mlit import (
    MLIT_ATTRIBUTION,
    MlitGisRequired,
    assign_stations_to_wards,
    parse_station_features,
)

_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "sample"
SAMPLE_PATH = _DATA_DIR / "mlit_stations_sample.json"


@pytest.fixture
def records() -> list[dict]:
    geojson = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    return parse_station_features(geojson)


def test_parse_extracts_records_with_area_code(records: list[dict]) -> None:
    assert len(records) == 13  # all features parsed
    assert {"area_code", "station_name", "line", "lon", "lat"} <= set(records[0])
    shinjuku = next(r for r in records if r["station_name"] == "新宿")
    assert shinjuku["area_code"] == "13104"
    assert shinjuku["lon"] is not None


def test_count_dedupes_multiline_drops_unassigned_and_filters_wards(records: list[dict]) -> None:
    counts = count_stations_by_ward(records)
    by_code = dict(zip(counts["area_code"], counts["station_count"], strict=False))

    # Shinjuku appears on two lines -> counted once; 3 distinct stations in 13104.
    assert by_code["13104"] == 3
    assert by_code["13101"] == 2
    assert by_code["13113"] == 4
    assert by_code["13114"] == 1
    # Non-Tokyo (14100) filtered; the no-area_code feature dropped.
    assert "14100" not in by_code


def test_build_sample_is_not_real(records: list[dict]) -> None:
    layer = build_accessibility_layer(records)  # default sample
    assert (layer["source_mode"] == SOURCE_MODE_SAMPLE).all()
    assert layer["data_basis"].str.startswith("sample fixture").all()
    assert not layer["data_basis"].str.startswith("public:").any()
    assert (layer["attribution"] == MLIT_ATTRIBUTION).all()
    assert classify_accessibility_layer(layer) == "sample_fixture"
    assert classify_accessibility_layer(layer) != "live_public"

    assert layer.iloc[0]["area"] == "Shibuya"  # 4 stations -> densest
    assert layer["accessibility_score"].max() == pytest.approx(100.0)
    assert layer["accessibility_score"].min() == pytest.approx(0.0)
    assert layer["accessibility_score"].is_monotonic_decreasing


def test_build_live_is_public(records: list[dict]) -> None:
    layer = build_accessibility_layer(records, source_mode=SOURCE_MODE_LIVE)
    assert (layer["source_mode"] == SOURCE_MODE_LIVE).all()
    assert layer["data_basis"].str.startswith("public:MLIT").all()
    assert classify_accessibility_layer(layer) == "live_public"


def test_per_capita_with_zero_and_missing_population(records: list[dict]) -> None:
    # Chiyoda has a real population; Shibuya is zero; others missing.
    population = {"13101": 66680, "13113": 0}
    layer = build_accessibility_layer(records, population_by_code=population)

    assert "station_count_per_10k" in layer.columns
    chiyoda = layer.loc[layer["area_code"] == "13101"].iloc[0]
    assert chiyoda["station_count_per_10k"] == pytest.approx(2 / 66680 * 10000)
    # Zero population -> NaN (guard against inf), missing population -> NaN.
    shibuya = layer.loc[layer["area_code"] == "13113"].iloc[0]
    assert pd.isna(shibuya["station_count_per_10k"])
    nakano = layer.loc[layer["area_code"] == "13114"].iloc[0]
    assert pd.isna(nakano["station_count_per_10k"])

    plain = build_accessibility_layer(records)
    assert "station_count_per_10k" not in plain.columns


def test_build_rejects_unknown_source_mode(records: list[dict]) -> None:
    with pytest.raises(ValueError, match="source_mode"):
        build_accessibility_layer(records, source_mode="totally-real")


def test_works_without_population(records: list[dict]) -> None:
    layer = build_accessibility_layer(records, population_by_code=None)
    assert "population" not in layer.columns
    assert len(layer) == 4


def test_classify_missing_and_unknown() -> None:
    assert classify_accessibility_layer(None) == "missing"
    assert classify_accessibility_layer(pd.DataFrame()) == "missing"
    no_mode = pd.DataFrame({"area": ["Shibuya"], "station_count": [4]})
    assert classify_accessibility_layer(no_mode) == "unknown"


def test_ward_assignment_is_deferred() -> None:
    # The GIS step is intentionally not implemented; it proposes the opt-in.
    with pytest.raises(MlitGisRequired, match="spatial join"):
        assign_stations_to_wards([])
