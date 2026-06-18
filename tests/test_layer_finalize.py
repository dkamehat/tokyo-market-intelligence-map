"""Tests for the shared ward-layer finalizer."""

from __future__ import annotations

import pandas as pd
import pytest

from tokyo_market_intel.ingestion.layer_finalize import finalize_ward_layer

WARDS = {"13101": "Chiyoda", "13104": "Shinjuku", "13113": "Shibuya"}


def _counts(values: dict[str, int]) -> pd.DataFrame:
    return pd.DataFrame({"area_code": list(values), "n": list(values.values())})


def test_minmax_score_and_sort() -> None:
    layer = finalize_ward_layer(
        _counts({"13101": 2, "13104": 6, "13113": 4}),
        value_col="n",
        score_col="score",
        ward_names=WARDS,
        source_mode="live_public",
        data_basis="public:test",
    )
    assert list(layer.columns) == ["area", "area_code", "n", "score", "source_mode", "data_basis"]
    assert layer.iloc[0]["area"] == "Shinjuku"  # highest value first
    assert layer["score"].max() == pytest.approx(100.0)
    assert layer["score"].min() == pytest.approx(0.0)
    assert layer["score"].is_monotonic_decreasing
    assert (layer["source_mode"] == "live_public").all()
    assert (layer["data_basis"] == "public:test").all()


def test_constant_values_are_neutral() -> None:
    layer = finalize_ward_layer(
        _counts({"13101": 5, "13104": 5}),
        value_col="n",
        score_col="score",
        ward_names=WARDS,
        source_mode="sample_fixture",
        data_basis="sample fixture",
    )
    # All-equal values -> neutral 50 (no artificial winner).
    assert (layer["score"] == 50.0).all()


def test_attribution_is_optional() -> None:
    without = finalize_ward_layer(
        _counts({"13101": 1}),
        value_col="n",
        score_col="score",
        ward_names=WARDS,
        source_mode="sample_fixture",
        data_basis="sample fixture",
    )
    assert "attribution" not in without.columns

    with_attr = finalize_ward_layer(
        _counts({"13101": 1}),
        value_col="n",
        score_col="score",
        ward_names=WARDS,
        source_mode="sample_fixture",
        data_basis="sample fixture",
        attribution="© Someone",
    )
    assert "attribution" in with_attr.columns
    assert (with_attr["attribution"] == "© Someone").all()


def test_per_capita_zero_and_missing_population_are_nan_never_inf() -> None:
    layer = finalize_ward_layer(
        _counts({"13101": 10, "13104": 10, "13113": 10}),
        value_col="n",
        score_col="score",
        ward_names=WARDS,
        source_mode="live_public",
        data_basis="public:test",
        population_by_code={"13101": 50000, "13104": 0},  # 13113 missing
        per_capita_col="n_per_10k",
    )
    chiyoda = layer.loc[layer["area_code"] == "13101"].iloc[0]
    assert chiyoda["n_per_10k"] == pytest.approx(10 / 50000 * 10000)
    # Zero population -> NaN (not inf); missing -> NaN.
    shinjuku = layer.loc[layer["area_code"] == "13104"].iloc[0]
    shibuya = layer.loc[layer["area_code"] == "13113"].iloc[0]
    assert pd.isna(shinjuku["n_per_10k"])
    assert pd.isna(shibuya["n_per_10k"])
    assert not layer["n_per_10k"].apply(lambda x: x == float("inf")).any()


def test_extra_cols_are_passed_through_after_score() -> None:
    counts = pd.DataFrame(
        {"area_code": ["13101", "13104"], "n": [3, 6], "mean": [3.0, 6.0], "obs": [2, 5]}
    )
    layer = finalize_ward_layer(
        counts,
        value_col="n",
        score_col="score",
        ward_names=WARDS,
        source_mode="live_public",
        data_basis="public:test",
        extra_cols=["mean", "obs"],
    )
    assert list(layer.columns) == [
        "area", "area_code", "n", "score", "mean", "obs", "source_mode", "data_basis"
    ]
    shinjuku = layer.loc[layer["area_code"] == "13104"].iloc[0]
    assert shinjuku["obs"] == 5


def test_no_per_capita_without_population() -> None:
    layer = finalize_ward_layer(
        _counts({"13101": 1}),
        value_col="n",
        score_col="score",
        ward_names=WARDS,
        source_mode="sample_fixture",
        data_basis="sample fixture",
        per_capita_col="n_per_10k",  # ignored without population
    )
    assert "population" not in layer.columns
    assert "n_per_10k" not in layer.columns
