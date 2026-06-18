"""Transform MLIT L01 land-price records into a Tokyo-23-ward cost-pressure layer.

Pure and unit-testable: takes land-price records (a list of ``dict`` with ``area_code``
and ``price``) and returns a ``pandas`` object. No network, no GIS.

Scope (fourth public-data integration):

- Source: MLIT 地価公示 (Land Price Public Notice), dataset L01.
- Grain: Tokyo 23 wards, keyed by the municipality code already present in L01 (so the
  aggregation is GIS-free).
- Output: a cost-pressure proxy = median (and mean) published land price per ward.

What this supports: a **cost-pressure proxy** only. Land price is NOT actual store
rent, operating cost, or profit margin. Higher land price -> higher cost pressure,
which is a **negative** factor in the Opportunity score.
"""

from __future__ import annotations

import pandas as pd

from ..sources.mlit_cost import L01_ATTRIBUTION
from .estat_population import TOKYO_23_WARD_CODES, TOKYO_23_WARDS
from .layer_finalize import finalize_ward_layer
from .provenance import SOURCE_MODE_LIVE, SOURCE_MODE_SAMPLE, classify_layer

DATA_BASIS_BY_MODE = {
    SOURCE_MODE_LIVE: "public:MLIT Land Price Public Notice L01 (land price/m2)",
    SOURCE_MODE_SAMPLE: "sample fixture: schema only, not authoritative",
}


def aggregate_cost_by_ward(records: list[dict]) -> pd.DataFrame:
    """Aggregate land-price records to per-ward median/mean/count.

    Drops records with no ``area_code`` or a non-numeric/missing ``price``; keeps only
    the 23 Tokyo wards. Returns ``area_code``, ``land_price_median``,
    ``land_price_mean``, ``observation_count``.
    """

    frame = pd.DataFrame(
        [{"area_code": r.get("area_code"), "price": r.get("price")} for r in records],
        columns=["area_code", "price"],
    )
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame = frame.dropna(subset=["area_code", "price"])
    frame = frame[frame["area_code"].isin(TOKYO_23_WARD_CODES)]

    grouped = frame.groupby("area_code")["price"]
    return pd.DataFrame(
        {
            "land_price_median": grouped.median(),
            "land_price_mean": grouped.mean(),
            "observation_count": grouped.size(),
        }
    ).reset_index()


def build_cost_layer(
    records: list[dict],
    source_mode: str = SOURCE_MODE_SAMPLE,
) -> pd.DataFrame:
    """Build the Tokyo-23-ward cost-pressure layer from L01 records.

    Columns: ``area``, ``area_code``, ``land_price_median``, ``cost_pressure_score``,
    ``land_price_mean``, ``observation_count``, ``source_mode``, ``data_basis``,
    ``attribution``. ``cost_pressure_score`` is the median land price min-max scaled to
    0..100 (higher price -> higher cost pressure). Sorted by score descending.

    ``source_mode`` defaults to the conservative ``sample_fixture``.
    """

    if source_mode not in DATA_BASIS_BY_MODE:
        raise ValueError(
            f"Unknown source_mode {source_mode!r}. "
            f"Expected one of {sorted(DATA_BASIS_BY_MODE)}."
        )

    return finalize_ward_layer(
        aggregate_cost_by_ward(records),
        value_col="land_price_median",
        score_col="cost_pressure_score",
        ward_names=TOKYO_23_WARDS,
        source_mode=source_mode,
        data_basis=DATA_BASIS_BY_MODE[source_mode],
        extra_cols=["land_price_mean", "observation_count"],
        attribution=L01_ATTRIBUTION,
    )


def classify_cost_layer(layer: pd.DataFrame | None) -> str:
    """Classify a cost layer's provenance (delegates to ``classify_layer``)."""

    return classify_layer(layer)
