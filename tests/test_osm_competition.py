"""Unit tests for the OSM competition-density transform and provenance.

No network; pass offline.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tokyo_market_intel.ingestion.osm_competition import (
    SOURCE_MODE_LIVE,
    SOURCE_MODE_SAMPLE,
    build_competition_layer,
    classify_competition_layer,
    count_pois_by_ward,
)
from tokyo_market_intel.sources.overpass import OSM_ATTRIBUTION

_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "sample"
SAMPLE_PATH = _DATA_DIR / "osm_convenience_sample.json"


@pytest.fixture
def elements() -> list[dict]:
    payload = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    return payload["elements"]


def test_count_dedupes_drops_missing_coords_and_filters_wards(elements: list[dict]) -> None:
    counts = count_pois_by_ward(elements)
    by_code = dict(zip(counts["area_code"], counts["poi_count"], strict=False))

    # 13101: 3 valid (one missing-coords node dropped).
    assert by_code["13101"] == 3
    # 13104: 5 unique (the duplicate id 2005 counted once).
    assert by_code["13104"] == 5
    assert by_code["13113"] == 4
    assert by_code["13114"] == 2
    # Non-Tokyo area (14100) is filtered out.
    assert "14100" not in by_code


def test_build_competition_layer_sample_is_not_real(elements: list[dict]) -> None:
    layer = build_competition_layer(elements)  # default sample mode
    assert (layer["source_mode"] == SOURCE_MODE_SAMPLE).all()
    assert layer["data_basis"].str.startswith("sample fixture").all()
    assert not layer["data_basis"].str.startswith("public:").any()
    assert (layer["attribution"] == OSM_ATTRIBUTION).all()
    assert classify_competition_layer(layer) == "sample_fixture"
    assert classify_competition_layer(layer) != "live_public"

    # Densest ward (Shinjuku, 5) ranks first; scores are 0..100.
    assert layer.iloc[0]["area"] == "Shinjuku"
    assert layer["commercial_density_score"].max() == pytest.approx(100.0)
    assert layer["commercial_density_score"].min() == pytest.approx(0.0)
    assert layer["commercial_density_score"].is_monotonic_decreasing


def test_build_competition_layer_live_is_public(elements: list[dict]) -> None:
    layer = build_competition_layer(elements, source_mode=SOURCE_MODE_LIVE)
    assert (layer["source_mode"] == SOURCE_MODE_LIVE).all()
    assert layer["data_basis"].str.startswith("public:OpenStreetMap").all()
    assert classify_competition_layer(layer) == "live_public"


def test_per_capita_density_with_and_without_population(elements: list[dict]) -> None:
    population = {"13104": 349385, "13101": 66680}  # Shinjuku, Chiyoda only
    layer = build_competition_layer(elements, population_by_code=population)

    assert "poi_per_10k" in layer.columns
    shinjuku = layer.loc[layer["area_code"] == "13104"].iloc[0]
    assert shinjuku["poi_per_10k"] == pytest.approx(5 / 349385 * 10000)
    # Wards without a population entry get NaN, not a fabricated value.
    shibuya = layer.loc[layer["area_code"] == "13113"].iloc[0]
    assert pd.isna(shibuya["poi_per_10k"])

    # Without population, no per-capita columns are produced.
    plain = build_competition_layer(elements)
    assert "poi_per_10k" not in plain.columns


def test_per_capita_zero_population_is_nan_never_inf(elements: list[dict]) -> None:
    # Guard parity with the shared finalizer: zero population -> NaN, not inf.
    layer = build_competition_layer(elements, population_by_code={"13104": 0})
    shinjuku = layer.loc[layer["area_code"] == "13104"].iloc[0]
    assert pd.isna(shinjuku["poi_per_10k"])
    assert not layer["poi_per_10k"].apply(lambda x: x == float("inf")).any()


def test_build_rejects_unknown_source_mode(elements: list[dict]) -> None:
    with pytest.raises(ValueError, match="source_mode"):
        build_competition_layer(elements, source_mode="totally-real")


def test_classify_missing_and_unknown() -> None:
    assert classify_competition_layer(None) == "missing"
    assert classify_competition_layer(pd.DataFrame()) == "missing"
    no_mode = pd.DataFrame({"area": ["Shinjuku"], "poi_count": [5]})
    assert classify_competition_layer(no_mode) == "unknown"
