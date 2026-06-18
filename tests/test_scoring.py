import numpy as np
import pandas as pd
import pytest

from tokyo_market_intel import ScoreWeights, compute_opportunity_scores, minmax_scale


def test_minmax_scale_basic_range() -> None:
    series = pd.Series([10, 20, 30])

    scaled = minmax_scale(series)

    assert scaled.tolist() == [0.0, 50.0, 100.0]


def test_minmax_scale_constant_returns_neutral() -> None:
    series = pd.Series([5, 5, 5])

    scaled = minmax_scale(series)

    assert scaled.tolist() == [50.0, 50.0, 50.0]


def test_minmax_scale_preserves_missing_values() -> None:
    series = pd.Series([1, np.nan, 3])

    scaled = minmax_scale(series)

    assert scaled.iloc[0] == 0.0
    assert np.isnan(scaled.iloc[1])
    assert scaled.iloc[2] == 100.0


def test_compute_opportunity_scores_orders_rows() -> None:
    df = pd.DataFrame(
        {
            "area": ["Area A", "Area B"],
            "demand_score": [90, 40],
            "accessibility_score": [80, 30],
            "growth_score": [60, 40],
            "competition_pressure": [20, 70],
            "cost_pressure": [30, 60],
            "uncertainty_penalty": [10, 80],
        }
    )

    result = compute_opportunity_scores(df, ScoreWeights())

    assert result.iloc[0]["area"] == "Area A"
    assert result.iloc[0]["confidence_label"] == "High"
    assert result.iloc[1]["confidence_label"] == "Low"


def test_compute_opportunity_scores_requires_columns() -> None:
    df = pd.DataFrame({"demand_score": [1]})

    with pytest.raises(ValueError, match="Missing required columns"):
        compute_opportunity_scores(df, ScoreWeights())


def test_negative_weights_are_rejected() -> None:
    df = pd.DataFrame(
        {
            "demand_score": [50],
            "accessibility_score": [50],
            "growth_score": [50],
            "competition_pressure": [50],
            "cost_pressure": [50],
            "uncertainty_penalty": [50],
        }
    )

    with pytest.raises(ValueError, match="must be non-negative"):
        compute_opportunity_scores(df, ScoreWeights(demand=-1))
