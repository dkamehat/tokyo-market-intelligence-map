"""Unit tests for the e-Stat daytime-activity transform (no network)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tokyo_market_intel.ingestion.estat_daytime import (
    SOURCE_MODE_LIVE,
    SOURCE_MODE_SAMPLE,
    build_daytime_layer,
    classify_daytime_layer,
)
from tokyo_market_intel.ingestion.estat_population import TOKYO_23_WARDS

_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "sample"
SAMPLE_PATH = _DATA_DIR / "estat_daytime_sample.json"
DAYTIME_FILTER = {"@cat01": "01", "@cat02": "000"}


@pytest.fixture
def payload() -> dict:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def test_build_keeps_only_23_wards_and_scores(payload: dict) -> None:
    layer = build_daytime_layer(payload, value_filter=DAYTIME_FILTER, source_mode=SOURCE_MODE_LIVE)
    # Yokohama (14100) dropped; only Tokyo wards remain (6 in the fixture).
    assert set(layer["area_code"]).issubset(TOKYO_23_WARDS.keys())
    assert "14100" not in set(layer["area_code"])
    assert len(layer) == 6

    assert "daytime_population" in layer.columns
    assert "daytime_activity_score" in layer.columns
    # min-max 0..100, sorted descending; Minato (highest daytime) first.
    assert layer["daytime_activity_score"].max() == pytest.approx(100.0)
    assert layer["daytime_activity_score"].min() == pytest.approx(0.0)
    assert layer["daytime_activity_score"].is_monotonic_decreasing
    assert layer.iloc[0]["area"] == "Minato"


def test_daytime_selects_daytime_not_nighttime(payload: dict) -> None:
    layer = build_daytime_layer(payload, value_filter=DAYTIME_FILTER, source_mode=SOURCE_MODE_LIVE)
    chiyoda = layer.loc[layer["area_code"] == "13101"].iloc[0]
    # Daytime cell (1,169,000), NOT the nighttime cell (66,680).
    assert chiyoda["daytime_population"] == 1169000


def test_attribution_present_and_scores_finite(payload: dict) -> None:
    layer = build_daytime_layer(payload, value_filter=DAYTIME_FILTER, source_mode=SOURCE_MODE_LIVE)
    assert (layer["attribution"].str.contains("令和2年国勢調査")).all()
    assert np.isfinite(layer["daytime_activity_score"]).all()
    assert not layer["daytime_activity_score"].isna().any()


def test_optional_resident_ratio_is_guarded(payload: dict) -> None:
    resident = {"13101": 66680.0, "13103": 260486.0, "13104": 0.0}  # one zero -> NaN ratio
    layer = build_daytime_layer(
        payload,
        value_filter=DAYTIME_FILTER,
        source_mode=SOURCE_MODE_LIVE,
        resident_population_by_code=resident,
    ).set_index("area_code")
    assert "resident_population_reference" in layer.columns
    assert "daytime_to_resident_ratio" in layer.columns
    # Chiyoda ratio = 1,169,000 / 66,680 ~ 17.5 (the key day-vs-night contrast).
    assert layer.loc["13101", "daytime_to_resident_ratio"] == pytest.approx(17.53, abs=0.1)
    # Zero resident population -> guarded to NaN, never inf.
    assert pd.isna(layer.loc["13104", "daytime_to_resident_ratio"])
    assert np.isfinite(layer["daytime_to_resident_ratio"].dropna()).all()


def test_without_resident_map_no_ratio_columns(payload: dict) -> None:
    layer = build_daytime_layer(
        payload, value_filter=DAYTIME_FILTER, source_mode=SOURCE_MODE_SAMPLE
    )
    assert "daytime_to_resident_ratio" not in layer.columns
    assert "resident_population_reference" not in layer.columns


def test_sample_is_never_classified_real(payload: dict) -> None:
    layer = build_daytime_layer(payload, value_filter=DAYTIME_FILTER)  # default sample
    assert (layer["source_mode"] == SOURCE_MODE_SAMPLE).all()
    assert classify_daytime_layer(layer) == "sample_fixture"
    assert classify_daytime_layer(layer) != "live_public"


def test_live_is_classified_live(payload: dict) -> None:
    layer = build_daytime_layer(payload, value_filter=DAYTIME_FILTER, source_mode=SOURCE_MODE_LIVE)
    assert (layer["source_mode"] == SOURCE_MODE_LIVE).all()
    assert classify_daytime_layer(layer) == "live_public"


def test_rejects_unknown_source_mode(payload: dict) -> None:
    with pytest.raises(ValueError, match="source_mode"):
        build_daytime_layer(payload, value_filter=DAYTIME_FILTER, source_mode="totally-real")
