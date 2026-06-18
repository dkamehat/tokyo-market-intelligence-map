"""Shared final-shaping for ward-grain public-data layers.

Every layer (Demand, Competition, Accessibility, future Cost) ends the same way: map
ward names, min-max a value column into a 0..100 score, optionally compute a per-capita
density, then stamp provenance (``source_mode``/``data_basis``) and an optional
attribution, in a stable column order, sorted by score. This function is the single
implementation of that shape so the layers cannot drift apart.
"""

from __future__ import annotations

import pandas as pd

from tokyo_market_intel.scoring import minmax_scale


def finalize_ward_layer(
    counts: pd.DataFrame,
    *,
    value_col: str,
    score_col: str,
    ward_names: dict[str, str],
    source_mode: str,
    data_basis: str,
    extra_cols: list[str] | None = None,
    attribution: str | None = None,
    population_by_code: dict[str, float] | None = None,
    per_capita_col: str | None = None,
    per_capita_scale: float = 10000.0,
) -> pd.DataFrame:
    """Finalize a ward-grain layer from a ``counts`` frame.

    ``counts`` must have ``area_code`` and ``value_col``. Returns columns:
    ``area``, ``area_code``, ``value_col``, ``score_col``, any ``extra_cols``
    (passed through from ``counts``), optionally ``population`` + ``per_capita_col``,
    then ``source_mode``, ``data_basis``, and ``attribution`` (only when provided).

    - ``score_col`` is ``value_col`` min-max scaled to 0..100 across the rows present.
    - ``extra_cols`` keeps additional already-computed columns (e.g. a mean and an
      observation count) in the output, after the score.
    - Per-capita (when ``population_by_code`` and ``per_capita_col`` are given) divides
      by population with a **zero/missing guard**: non-positive or missing population
      yields NaN, never ``inf``.
    - Rows are sorted by ``score_col`` descending.
    """

    layer = counts.copy()
    layer["area"] = layer["area_code"].map(ward_names)
    layer[score_col] = minmax_scale(layer[value_col])

    columns = ["area", "area_code", value_col, score_col]
    if extra_cols:
        columns += [column for column in extra_cols if column in layer.columns]

    if population_by_code and per_capita_col is not None:
        population = layer["area_code"].map(population_by_code).astype("float64")
        # zero/null guard: non-positive or missing population -> NaN (never inf).
        population = population.where(population > 0)
        layer["population"] = population
        layer[per_capita_col] = layer[value_col] / population * per_capita_scale
        columns += ["population", per_capita_col]

    layer["source_mode"] = source_mode
    layer["data_basis"] = data_basis
    columns += ["source_mode", "data_basis"]

    if attribution is not None:
        layer["attribution"] = attribution
        columns += ["attribution"]

    layer = layer[columns]
    return layer.sort_values(score_col, ascending=False).reset_index(drop=True)
