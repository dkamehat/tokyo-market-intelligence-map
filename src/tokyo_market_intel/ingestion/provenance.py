"""Shared provenance machinery for public-data layers.

Every public-data layer (e-Stat Demand, OSM Competition, future MLIT layers) labels its
rows with a ``source_mode`` so the UI can decide whether a layer may be shown as REAL.
This module is the single source of truth for those mode values and the classification
logic, so the rule lives in exactly one place.
"""

from __future__ import annotations

import pandas as pd

# A layer is only ever shown as REAL when its rows are ``live_public``. Sample-fixture
# output is never treated as real. The conservative default for builders is
# ``SOURCE_MODE_SAMPLE`` so sample data can never be mislabeled as real.
SOURCE_MODE_LIVE = "live_public"
SOURCE_MODE_SAMPLE = "sample_fixture"


def classify_layer(
    layer: pd.DataFrame | None,
    source_mode_column: str = "source_mode",
) -> str:
    """Classify a layer's provenance for safe UI rendering.

    Returns one of:

    - ``"missing"`` — no layer or an empty layer.
    - ``"live_public"`` — every row is real public data (safe to label REAL).
    - ``"sample_fixture"`` — every row is schema-fixture data (NOT real).
    - ``"unknown"`` — no provenance column, or mixed / unrecognized values; treated as
      not real.
    """

    if layer is None or len(layer) == 0:
        return "missing"
    if source_mode_column not in layer.columns:
        return "unknown"

    modes = set(layer[source_mode_column].dropna().unique())
    if modes == {SOURCE_MODE_LIVE}:
        return "live_public"
    if modes == {SOURCE_MODE_SAMPLE}:
        return "sample_fixture"
    return "unknown"
