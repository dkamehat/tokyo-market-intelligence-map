"""Scoring utilities for Tokyo Market Intelligence Map.

The functions in this module intentionally stay simple and inspectable.
They should be the single source of truth for opportunity scoring.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ScoreWeights:
    """Scenario weights for opportunity scoring.

    All weights must be non-negative. Penalty fields are subtracted from the
    opportunity score, while positive fields are added.
    """

    demand: float = 1.0
    accessibility: float = 1.0
    growth: float = 0.5
    competition: float = 0.7
    cost: float = 0.5
    uncertainty: float = 0.8

    def validate(self) -> None:
        for field_name, value in self.__dict__.items():
            if value < 0:
                raise ValueError(f"Weight `{field_name}` must be non-negative, got {value}.")


def minmax_scale(series: pd.Series) -> pd.Series:
    """Scale a numeric pandas Series to 0..100.

    Missing values are preserved. If all non-null values are identical, return
    50 for non-null rows to avoid creating artificial winners.
    """

    numeric = pd.to_numeric(series, errors="coerce")
    non_null = numeric.dropna()

    if non_null.empty:
        return pd.Series(np.nan, index=series.index, dtype="float64")

    min_value = non_null.min()
    max_value = non_null.max()

    if min_value == max_value:
        return pd.Series(np.where(numeric.notna(), 50.0, np.nan), index=series.index)

    return ((numeric - min_value) / (max_value - min_value) * 100).astype("float64")


def _require_columns(df: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")


def compute_opportunity_scores(df: pd.DataFrame, weights: ScoreWeights) -> pd.DataFrame:
    """Compute opportunity scores from normalized score columns.

    Required input columns are expected to be 0..100 scores:

    - demand_score
    - accessibility_score
    - growth_score
    - competition_pressure
    - cost_pressure
    - uncertainty_penalty

    The function returns a copy of the dataframe with `opportunity_score` and
    `confidence_label` added.
    """

    weights.validate()

    required = [
        "demand_score",
        "accessibility_score",
        "growth_score",
        "competition_pressure",
        "cost_pressure",
        "uncertainty_penalty",
    ]
    _require_columns(df, required)

    output = df.copy()
    score_columns = output[required].apply(pd.to_numeric, errors="coerce")

    output["opportunity_score"] = (
        weights.demand * score_columns["demand_score"]
        + weights.accessibility * score_columns["accessibility_score"]
        + weights.growth * score_columns["growth_score"]
        - weights.competition * score_columns["competition_pressure"]
        - weights.cost * score_columns["cost_pressure"]
        - weights.uncertainty * score_columns["uncertainty_penalty"]
    )

    output["confidence_label"] = np.select(
        [
            score_columns["uncertainty_penalty"] <= 25,
            score_columns["uncertainty_penalty"] <= 60,
        ],
        ["High", "Medium"],
        default="Low",
    )

    return output.sort_values("opportunity_score", ascending=False).reset_index(drop=True)
