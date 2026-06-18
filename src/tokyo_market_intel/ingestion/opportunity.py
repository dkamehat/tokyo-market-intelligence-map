"""Integrate the public-data layers into a ward-grain Opportunity screening score.

Joins the four layers — Demand (e-Stat), Accessibility (MLIT N02), Competition (OSM),
Cost (MLIT L01) — on the Tokyo-23-ward code spine and computes:

- ``opportunity_score`` — a weighted combination (positives added, pressures subtracted).
- ``data_uncertainty_penalty`` + ``confidence_label`` — from how many layers are present
  and live for each ward.

This is **first-cut market-intelligence / opportunity screening from public data**. It
is NOT a revenue forecast, demand forecast, or profitability estimate, and public data
alone is not a final investment decision — internal company data would be needed for
revenue-impact analysis.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .estat_population import TOKYO_23_WARDS
from .provenance import SOURCE_MODE_LIVE, SOURCE_MODE_SAMPLE, classify_layer

# A REAL opportunity ranking needs at least this many live_public layers.
MIN_LIVE_LAYERS_FOR_REAL = 2

# Missing scores are filled with this neutral midpoint so the score is computable; the
# gap is instead reflected in the uncertainty penalty.
NEUTRAL_SCORE = 50.0

# Daytime activity is a positive *refinement of the Demand axis* (resident population vs.
# daytime/commuter activity). It is scored as an additive positive term but, because it
# overlaps the existing Demand layer, it deliberately does NOT count toward the 4-layer
# coverage / confidence math. Its default weight is 0, so the baseline ranking, penalty,
# and confidence are unchanged until a scenario raises the daytime weight.
DAYTIME_SCORE_COL = "daytime_activity_score"

CAVEAT = (
    "First-cut opportunity screening from public data — not a revenue, demand, or "
    "profitability estimate. Internal company data would be needed for revenue impact."
)

# (layer key, source score column, unified column, OpportunityWeights field, is_positive)
# is_positive drives the sign in the score so adding a layer (e.g. Growth) only needs a
# spec row — the formula reads the sign from here, it is not hardcoded.
_LAYER_SPECS = [
    ("demand", "demand_score", "demand_score", "demand", True),
    ("accessibility", "accessibility_score", "accessibility_score", "accessibility", True),
    ("competition", "commercial_density_score", "competition_pressure", "competition", False),
    ("cost", "cost_pressure_score", "cost_pressure", "cost", False),
]
_UNIFIED_COLS = ["demand_score", "accessibility_score", "competition_pressure", "cost_pressure"]

_OUTPUT_COLS = [
    "area",
    "area_code",
    "opportunity_score",
    "confidence_label",
    "demand_score",
    DAYTIME_SCORE_COL,
    "accessibility_score",
    "competition_pressure",
    "cost_pressure",
    "data_uncertainty_penalty",
    "available_layer_count",
    "live_layer_count",
    "missing_layer_count",
    "source_mode",
    "data_basis",
    "caveat",
]


@dataclass(frozen=True)
class OpportunityWeights:
    """Weights for the opportunity score (positives added, pressures subtracted)."""

    demand: float = 1.0
    accessibility: float = 1.0
    competition: float = 0.7
    cost: float = 0.5
    uncertainty: float = 0.5
    # Daytime activity is a Demand-axis refinement; default 0 keeps the baseline ranking.
    daytime: float = 0.0


DEFAULT_WEIGHTS = OpportunityWeights()


def count_live_layers(layers: dict[str, pd.DataFrame | None]) -> int:
    """Count layers that are real public data (``live_public``)."""

    return sum(1 for layer in layers.values() if classify_layer(layer) == SOURCE_MODE_LIVE)


def integrate_opportunity(
    layers: dict[str, pd.DataFrame | None],
    *,
    weights: OpportunityWeights = DEFAULT_WEIGHTS,
    source_mode: str = SOURCE_MODE_SAMPLE,
    daytime_layer: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Integrate the four layers into an opportunity-screening table.

    ``layers`` maps ``"demand"|"accessibility"|"competition"|"cost"`` to a layer
    DataFrame or ``None``. Returns one row per ward present in any layer, with the
    columns in :data:`_OUTPUT_COLS`, sorted by ``opportunity_score`` descending.

    ``source_mode`` stamps the output's provenance (the caller decides whether this is a
    REAL or a sample/demo integration). Per-ward confidence is computed from the actual
    layer provenance regardless.

    ``daytime_layer`` is an optional Demand-axis refinement (e-Stat daytime population).
    Its ``daytime_activity_score`` is added as a positive term weighted by
    ``weights.daytime`` (default 0). It deliberately does **not** affect the 4-layer
    coverage / confidence math, because it overlaps the resident Demand layer — so at the
    default weight the ranking, penalty, and confidence are identical to a 4-layer run.
    """

    classes = {key: classify_layer(layers.get(key)) for key, *_ in _LAYER_SPECS}

    codes: set[str] = set()
    subs: dict[str, pd.DataFrame] = {}
    for key, src, dst, _weight_attr, _is_positive in _LAYER_SPECS:
        layer = layers.get(key)
        if classes[key] != "missing" and src in layer.columns:
            sub = layer[["area_code", src]].rename(columns={src: dst}).copy()
            sub["area_code"] = sub["area_code"].astype(str)
            subs[dst] = sub
            codes |= set(sub["area_code"])

    if not codes:
        return pd.DataFrame(columns=_OUTPUT_COLS)

    out = pd.DataFrame({"area_code": sorted(codes)})
    for _key, _src, dst, _weight_attr, _is_positive in _LAYER_SPECS:
        if dst in subs:
            out = out.merge(subs[dst], on="area_code", how="left")
        else:
            out[dst] = np.nan
        out[dst] = pd.to_numeric(out[dst], errors="coerce")

    # Daytime activity (Demand-axis refinement): merge its score for the wards already on
    # the 4-layer spine. NaN where absent; never contributes new wards or coverage counts.
    if daytime_layer is not None and DAYTIME_SCORE_COL in getattr(daytime_layer, "columns", []):
        daytime = daytime_layer[["area_code", DAYTIME_SCORE_COL]].copy()
        daytime["area_code"] = daytime["area_code"].astype(str)
        out = out.merge(daytime, on="area_code", how="left")
    else:
        out[DAYTIME_SCORE_COL] = np.nan
    out[DAYTIME_SCORE_COL] = pd.to_numeric(out[DAYTIME_SCORE_COL], errors="coerce")

    present_flags, live_flags = [], []
    for key, _src, dst, _weight_attr, _is_positive in _LAYER_SPECS:
        present = out[dst].notna()
        present_flags.append(present)
        live_flags.append(present & (classes[key] == SOURCE_MODE_LIVE))

    out["available_layer_count"] = sum(present_flags).astype(int)
    out["live_layer_count"] = sum(live_flags).astype(int)
    out["missing_layer_count"] = len(_LAYER_SPECS) - out["available_layer_count"]
    nonlive_present = out["available_layer_count"] - out["live_layer_count"]

    out["data_uncertainty_penalty"] = (
        100.0 * (out["missing_layer_count"] + 0.5 * nonlive_present) / len(_LAYER_SPECS)
    ).round(1)

    out["confidence_label"] = np.where(
        nonlive_present > 0,
        "Low",
        np.where(
            out["live_layer_count"] >= 3,
            "High",
            np.where(out["live_layer_count"] == 2, "Medium", "Low"),
        ),
    )

    # Sign and weight come from the layer spec, so positives add and pressures subtract
    # without hardcoding — a new layer (e.g. Growth) just needs a spec row.
    score = pd.Series(0.0, index=out.index)
    for _key, _src, dst, weight_attr, is_positive in _LAYER_SPECS:
        sign = 1.0 if is_positive else -1.0
        weight = getattr(weights, weight_attr)
        score = score + sign * weight * out[dst].fillna(NEUTRAL_SCORE)
    # Daytime activity adds as a positive Demand-axis term; weight 0 by default => no-op.
    score = score + weights.daytime * out[DAYTIME_SCORE_COL].fillna(NEUTRAL_SCORE)
    score = score - weights.uncertainty * out["data_uncertainty_penalty"]
    out["opportunity_score"] = score.round(2)

    out["area"] = out["area_code"].map(TOKYO_23_WARDS)
    out["source_mode"] = source_mode
    out["data_basis"] = (
        "public:integrated Demand/Accessibility/Competition/Cost (opportunity screening)"
        if source_mode == SOURCE_MODE_LIVE
        else "sample fixture: integration demo, not authoritative"
    )
    out["caveat"] = CAVEAT

    out = out[_OUTPUT_COLS]
    return out.sort_values("opportunity_score", ascending=False).reset_index(drop=True)


def classify_opportunity(layer: pd.DataFrame | None) -> str:
    """Classify an opportunity table's provenance (delegates to ``classify_layer``)."""

    return classify_layer(layer)
