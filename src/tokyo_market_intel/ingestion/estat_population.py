"""Transform e-Stat ``getStatsData`` payloads into a Tokyo-23-ward demand layer.

This module is pure and unit-testable: every function takes a parsed JSON payload
(a ``dict``) and returns a ``pandas`` object. No network access happens here.

Scope (first public-data integration):

- Source: e-Stat Population Census, total population by municipality.
- Grain: Tokyo 23 special wards (区), keyed by the standard 5-digit municipality code.
- Output: a Demand layer where ``demand_score`` is the min-max scaled population.

What this supports: a **demographic / household-structure demand proxy** only. It is
NOT a measure of income, purchasing power, or actual demand.
"""

from __future__ import annotations

import pandas as pd

from ..sources.estat import EstatApiError
from .layer_finalize import finalize_ward_layer
from .provenance import SOURCE_MODE_LIVE, SOURCE_MODE_SAMPLE, classify_layer

# Tokyo 23 special wards: standard municipality code -> romaji name.
# These codes (JIS X 0402, 5-digit) are stable identifiers and form the join spine
# that later layers (OSM, MLIT) attach to.
TOKYO_23_WARDS: dict[str, str] = {
    "13101": "Chiyoda",
    "13102": "Chuo",
    "13103": "Minato",
    "13104": "Shinjuku",
    "13105": "Bunkyo",
    "13106": "Taito",
    "13107": "Sumida",
    "13108": "Koto",
    "13109": "Shinagawa",
    "13110": "Meguro",
    "13111": "Ota",
    "13112": "Setagaya",
    "13113": "Shibuya",
    "13114": "Nakano",
    "13115": "Suginami",
    "13116": "Toshima",
    "13117": "Kita",
    "13118": "Arakawa",
    "13119": "Itabashi",
    "13120": "Nerima",
    "13121": "Adachi",
    "13122": "Katsushika",
    "13123": "Edogawa",
}

# Provenance mode values are shared (see provenance.py); re-exported here for callers
# and tests that import them from this module.

# Human-readable basis per mode. Kept explicit so every CSV/row is self-describing
# and a sample-built table can never be mistaken for real public data.
DATA_BASIS_BY_MODE = {
    SOURCE_MODE_LIVE: "public:e-Stat Population Census (total population)",
    SOURCE_MODE_SAMPLE: "sample fixture: schema only, not authoritative",
}

# Convenience export for callers that only need the ward codes (e.g. to scope a
# live API request). Avoids importing the full name map.
TOKYO_23_WARD_CODES = tuple(TOKYO_23_WARDS.keys())


def _as_list(value: object) -> list:
    """e-Stat collapses single-element arrays to objects; normalize to a list."""

    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def check_result_status(payload: dict) -> None:
    """Raise :class:`EstatApiError` if the payload reports a non-success status."""

    try:
        result = payload["GET_STATS_DATA"]["RESULT"]
    except (KeyError, TypeError):
        raise EstatApiError("Unexpected e-Stat payload: missing GET_STATS_DATA.RESULT.") from None

    status = result.get("STATUS")
    if status not in (0, "0"):
        message = result.get("ERROR_MSG", "unknown error")
        raise EstatApiError(f"e-Stat API error status {status}: {message}")


def extract_area_values(payload: dict, value_filter: dict[str, str] | None = None) -> pd.DataFrame:
    """Extract ``(area_code, value)`` rows from a ``getStatsData`` payload.

    ``value_filter`` keeps only VALUE rows whose attributes match, e.g.
    ``{"@cat01": "000"}`` to select the "total" sex category. Values are coerced to
    numeric; suppressed / non-numeric cells (``-``, ``X``, ``***``) become NaN.

    Raises if, after filtering, a single area code still has multiple values
    (ambiguous: the caller must supply a tighter ``value_filter``).
    """

    check_result_status(payload)

    try:
        values = _as_list(
            payload["GET_STATS_DATA"]["STATISTICAL_DATA"]["DATA_INF"]["VALUE"]
        )
    except (KeyError, TypeError):
        raise EstatApiError("Unexpected e-Stat payload: missing DATA_INF.VALUE.") from None

    rows: list[dict[str, object]] = []
    for item in values:
        if value_filter and any(item.get(key) != val for key, val in value_filter.items()):
            continue
        rows.append({"area_code": item.get("@area"), "value": item.get("$")})

    frame = pd.DataFrame(rows, columns=["area_code", "value"])
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")

    duplicates = frame["area_code"].value_counts()
    ambiguous = duplicates[duplicates > 1]
    if not ambiguous.empty:
        raise EstatApiError(
            "Multiple values per area after filtering "
            f"(e.g. area {ambiguous.index[0]}). Provide a tighter value_filter, such "
            'as {"@cat01": "000"} to select the total category.'
        )
    return frame


def build_demand_layer(
    payload: dict,
    value_filter: dict[str, str] | None = None,
    source_mode: str = SOURCE_MODE_SAMPLE,
) -> pd.DataFrame:
    """Build the Tokyo-23-ward Demand layer from a ``getStatsData`` payload.

    Returns columns: ``area``, ``area_code``, ``population``, ``demand_score``,
    ``source_mode``, ``data_basis``. ``demand_score`` is the population min-max scaled
    to 0..100 across the 23 wards. Sorted by ``demand_score`` descending.

    ``source_mode`` records provenance and **defaults to the conservative**
    ``sample_fixture`` so a caller can never accidentally publish sample data as real:
    real public data must be requested explicitly with ``SOURCE_MODE_LIVE``.
    """

    if source_mode not in DATA_BASIS_BY_MODE:
        raise ValueError(
            f"Unknown source_mode {source_mode!r}. "
            f"Expected one of {sorted(DATA_BASIS_BY_MODE)}."
        )

    values = extract_area_values(payload, value_filter=value_filter)

    demand = values[values["area_code"].isin(TOKYO_23_WARD_CODES)].rename(
        columns={"value": "population"}
    )
    return finalize_ward_layer(
        demand[["area_code", "population"]],
        value_col="population",
        score_col="demand_score",
        ward_names=TOKYO_23_WARDS,
        source_mode=source_mode,
        data_basis=DATA_BASIS_BY_MODE[source_mode],
    )


def classify_demand_layer(demand: pd.DataFrame | None) -> str:
    """Classify a demand layer's provenance for safe UI rendering.

    Backward-compatible wrapper delegating to the shared
    :func:`tokyo_market_intel.ingestion.provenance.classify_layer`.
    """

    return classify_layer(demand)
