"""Transform MLIT N02 station records into a Tokyo-23-ward accessibility layer.

Pure and unit-testable: takes station records (a list of ``dict``, each already
carrying an ``area_code``) and returns a ``pandas`` object. No network, no GIS here.

Scope (third public-data integration, minimal):

- Source: MLIT National Land Numerical Information, Railway data N02 (Station layer).
- Grain: Tokyo 23 wards, keyed by the same municipality-code spine as the other layers.
- Output: an accessibility proxy = station count per ward (optionally per-capita when
  the e-Stat population layer is supplied).

What this supports: a **station-access proxy** only. It is NOT demand, sales, or
willingness to buy — easy access to an area is not the same as a market for it.
"""

from __future__ import annotations

import pandas as pd

from ..sources.mlit import MLIT_ATTRIBUTION
from .estat_population import TOKYO_23_WARD_CODES, TOKYO_23_WARDS
from .layer_finalize import finalize_ward_layer
from .provenance import SOURCE_MODE_LIVE, SOURCE_MODE_SAMPLE, classify_layer

DATA_BASIS_BY_MODE = {
    SOURCE_MODE_LIVE: "public:MLIT National Land Numerical Information N02 (stations)",
    SOURCE_MODE_SAMPLE: "sample fixture: schema only, not authoritative",
}


def count_stations_by_ward(records: list[dict]) -> pd.DataFrame:
    """Count distinct stations per ward from station records.

    Rules: drop records with no ``area_code``; de-duplicate by ``(area_code,
    station_name)`` so a station served by several lines (multiple N02 features) counts
    once; keep only the 23 Tokyo wards.

    Returns columns ``area_code``, ``station_count``.
    """

    seen: set[tuple] = set()
    rows: list[dict[str, object]] = []
    for record in records:
        area_code = record.get("area_code")
        if not area_code:
            continue  # unassigned station -> unusable for ward counts
        key = (area_code, record.get("station_name"))
        if key in seen:
            continue  # same station across multiple lines
        seen.add(key)
        rows.append({"area_code": area_code})

    frame = pd.DataFrame(rows, columns=["area_code"])
    frame = frame[frame["area_code"].isin(TOKYO_23_WARD_CODES)]
    counts = frame.groupby("area_code").size().reset_index(name="station_count")
    return counts


def build_accessibility_layer(
    records: list[dict],
    source_mode: str = SOURCE_MODE_SAMPLE,
    population_by_code: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Build the Tokyo-23-ward accessibility layer from station records.

    Columns: ``area``, ``area_code``, ``station_count``, ``accessibility_score``,
    optionally ``population`` + ``station_count_per_10k``, then ``source_mode``,
    ``data_basis``, ``attribution``. ``accessibility_score`` is ``station_count``
    min-max scaled to 0..100 across the wards present. Sorted by score descending.

    ``source_mode`` defaults to the conservative ``sample_fixture``.
    """

    if source_mode not in DATA_BASIS_BY_MODE:
        raise ValueError(
            f"Unknown source_mode {source_mode!r}. "
            f"Expected one of {sorted(DATA_BASIS_BY_MODE)}."
        )

    return finalize_ward_layer(
        count_stations_by_ward(records),
        value_col="station_count",
        score_col="accessibility_score",
        ward_names=TOKYO_23_WARDS,
        source_mode=source_mode,
        data_basis=DATA_BASIS_BY_MODE[source_mode],
        attribution=MLIT_ATTRIBUTION,
        population_by_code=population_by_code,
        per_capita_col="station_count_per_10k",
    )


def classify_accessibility_layer(layer: pd.DataFrame | None) -> str:
    """Classify an accessibility layer's provenance (delegates to ``classify_layer``)."""

    return classify_layer(layer)
