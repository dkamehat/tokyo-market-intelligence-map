"""Transform Overpass POI elements into a Tokyo-23-ward competition-density layer.

Pure and unit-testable: every function takes parsed Overpass elements (a list of
``dict``) and returns a ``pandas`` object. No network access here.

Scope (second public-data integration):

- Source: OpenStreetMap ``shop=convenience`` POIs via the Overpass API.
- Grain: Tokyo 23 special wards, keyed by the same municipality-code spine as the
  e-Stat Demand layer (so the two layers join cleanly).
- Output: a competition / commercial-density proxy = POI count per ward (optionally a
  per-capita density when a population map is supplied).

What this supports: a **commercial-density / competition proxy** only. It is NOT a
measure of demand, sales, or revenue.

OSM data is ODbL: every output carries "© OpenStreetMap contributors".
"""

from __future__ import annotations

import pandas as pd

from ..sources.overpass import OSM_ATTRIBUTION
from .estat_population import TOKYO_23_WARD_CODES, TOKYO_23_WARDS
from .layer_finalize import finalize_ward_layer
from .provenance import SOURCE_MODE_LIVE, SOURCE_MODE_SAMPLE, classify_layer

# Provenance mode values are shared (see provenance.py); re-exported here for callers
# and tests that import them from this module.
DATA_BASIS_BY_MODE = {
    SOURCE_MODE_LIVE: "public:OpenStreetMap via Overpass (shop=convenience)",
    SOURCE_MODE_SAMPLE: "sample fixture: schema only, not authoritative",
}

# The single category selected for the first cut (stable tagging in Japan).
SELECTED_OSM_TAG = "shop=convenience"


def count_pois_by_ward(elements: list[dict]) -> pd.DataFrame:
    """Count POIs per ward from Overpass elements.

    Rules: drop elements with missing coordinates; de-duplicate by ``(type, id)`` so a
    POI returned under two adjacent ward queries is counted once; keep only the 23
    Tokyo wards (by the injected ``area_code``).

    Returns columns ``area_code``, ``poi_count``.
    """

    seen: set[tuple] = set()
    rows: list[dict[str, object]] = []
    for element in elements:
        if element.get("lat") is None or element.get("lon") is None:
            continue  # missing coordinates -> unusable
        key = (element.get("type"), element.get("id"))
        if key in seen:
            continue  # duplicate POI across ward queries
        seen.add(key)
        rows.append({"area_code": element.get("area_code")})

    frame = pd.DataFrame(rows, columns=["area_code"])
    frame = frame[frame["area_code"].isin(TOKYO_23_WARD_CODES)]
    counts = frame.groupby("area_code").size().reset_index(name="poi_count")
    return counts


def build_competition_layer(
    elements: list[dict],
    source_mode: str = SOURCE_MODE_SAMPLE,
    population_by_code: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Build the Tokyo-23-ward competition-density layer from Overpass elements.

    Columns: ``area``, ``area_code``, ``poi_count``, ``commercial_density_score``,
    optionally ``population`` + ``poi_per_10k``, then ``source_mode``, ``data_basis``,
    ``attribution``. ``commercial_density_score`` is ``poi_count`` min-max scaled to
    0..100 across the wards present. Sorted by score descending.

    ``source_mode`` defaults to the conservative ``sample_fixture`` so a caller can
    never accidentally publish sample data as real.

    Wards absent from the response are omitted (not asserted as zero).
    """

    if source_mode not in DATA_BASIS_BY_MODE:
        raise ValueError(
            f"Unknown source_mode {source_mode!r}. "
            f"Expected one of {sorted(DATA_BASIS_BY_MODE)}."
        )

    return finalize_ward_layer(
        count_pois_by_ward(elements),
        value_col="poi_count",
        score_col="commercial_density_score",
        ward_names=TOKYO_23_WARDS,
        source_mode=source_mode,
        data_basis=DATA_BASIS_BY_MODE[source_mode],
        attribution=OSM_ATTRIBUTION,
        population_by_code=population_by_code,
        per_capita_col="poi_per_10k",
    )


def classify_competition_layer(layer: pd.DataFrame | None) -> str:
    """Classify a competition layer's provenance for safe UI rendering.

    Backward-compatible wrapper delegating to the shared
    :func:`tokyo_market_intel.ingestion.provenance.classify_layer`.
    """

    return classify_layer(layer)
