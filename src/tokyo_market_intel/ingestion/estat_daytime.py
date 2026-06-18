"""Transform e-Stat ``getStatsData`` payloads into a Tokyo-23-ward daytime-activity layer.

Pure and unit-testable: every function takes a parsed JSON payload (a ``dict``) and
returns a ``pandas`` object. No network access happens here.

Scope (Demand-axis refinement):

- Source: e-Stat 令和2年国勢調査 従業地・通学地集計 — daytime population (昼間人口) by
  municipality.
- Grain: Tokyo 23 special wards, keyed by the standard 5-digit municipality code — the
  same spine as the resident-population Demand layer, so the two join directly.
- Output: ``daytime_activity_score`` = min-max scaled daytime population (0..100).

What this supports: a **daytime-activity proxy** (people present by place of work/
schooling). It is NOT actual demand, sales, revenue, or profit. It complements — does not
replace — the resident-population Demand layer (``demand_score``).
"""

from __future__ import annotations

import pandas as pd

from ..sources.estat_daytime import DAYTIME_ATTRIBUTION
from .estat_population import TOKYO_23_WARD_CODES, TOKYO_23_WARDS, extract_area_values
from .layer_finalize import finalize_ward_layer
from .provenance import SOURCE_MODE_LIVE, SOURCE_MODE_SAMPLE, classify_layer

DATA_BASIS_BY_MODE = {
    SOURCE_MODE_LIVE: "public:e-Stat 2020 Census daytime population (daytime-activity proxy)",
    SOURCE_MODE_SAMPLE: "sample fixture: schema only, not authoritative",
}


def build_daytime_layer(
    payload: dict,
    value_filter: dict[str, str] | None = None,
    source_mode: str = SOURCE_MODE_SAMPLE,
    resident_population_by_code: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Build the Tokyo-23-ward daytime-activity layer from a ``getStatsData`` payload.

    Returns columns: ``area``, ``area_code``, ``daytime_population``,
    ``daytime_activity_score``, optionally ``resident_population_reference`` +
    ``daytime_to_resident_ratio`` (display only — when ``resident_population_by_code`` is
    given), then ``source_mode``, ``data_basis``, ``attribution``. Sorted by score desc.

    ``value_filter`` selects the daytime + sex-total VALUE cell (the exact category codes
    are table-version specific; pass them via the CLI ``--cat-filter``). ``source_mode``
    **defaults to the conservative** ``sample_fixture`` so sample data can never be
    published as real.

    The optional ``daytime_to_resident_ratio`` is a **display-only** signal (daytime ÷
    resident population). It is NOT fed into the Opportunity score here — only
    ``daytime_activity_score`` is, via the Opportunity ``daytime`` weight.
    """

    if source_mode not in DATA_BASIS_BY_MODE:
        raise ValueError(
            f"Unknown source_mode {source_mode!r}. "
            f"Expected one of {sorted(DATA_BASIS_BY_MODE)}."
        )

    values = extract_area_values(payload, value_filter=value_filter)
    daytime = values[values["area_code"].isin(TOKYO_23_WARD_CODES)].rename(
        columns={"value": "daytime_population"}
    )

    per_capita_col = None
    extra_cols = None
    if resident_population_by_code is not None:
        # Display-only ratio = daytime / resident population (scale 1.0). The shared
        # finalizer guards against zero/missing population (NaN, never inf).
        per_capita_col = "daytime_to_resident_ratio"

    layer = finalize_ward_layer(
        daytime[["area_code", "daytime_population"]],
        value_col="daytime_population",
        score_col="daytime_activity_score",
        ward_names=TOKYO_23_WARDS,
        source_mode=source_mode,
        data_basis=DATA_BASIS_BY_MODE[source_mode],
        extra_cols=extra_cols,
        attribution=DAYTIME_ATTRIBUTION,
        population_by_code=resident_population_by_code,
        per_capita_col=per_capita_col,
        per_capita_scale=1.0,
    )
    # finalize_ward_layer names the population column "population"; rename it to make the
    # daytime layer self-describing (it is the resident reference, not daytime).
    if "population" in layer.columns:
        layer = layer.rename(columns={"population": "resident_population_reference"})
    return layer


def classify_daytime_layer(layer: pd.DataFrame | None) -> str:
    """Classify a daytime layer's provenance (delegates to ``classify_layer``)."""

    return classify_layer(layer)
