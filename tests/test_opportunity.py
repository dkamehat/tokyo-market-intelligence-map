"""Unit tests for the Opportunity Score integration (no network/file/API)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tokyo_market_intel.ingestion.opportunity import (
    _LAYER_SPECS,
    DEFAULT_WEIGHTS,
    OpportunityWeights,
    classify_opportunity,
    count_live_layers,
    integrate_opportunity,
)
from tokyo_market_intel.ingestion.provenance import SOURCE_MODE_LIVE, SOURCE_MODE_SAMPLE


def _layer(area_codes: list[str], score_col: str, values: list[float], mode: str) -> pd.DataFrame:
    return pd.DataFrame(
        {"area_code": area_codes, score_col: values, "source_mode": [mode] * len(area_codes)}
    )


def _all_live(codes: list[str], d, a, c, k) -> dict[str, pd.DataFrame]:
    return {
        "demand": _layer(codes, "demand_score", d, SOURCE_MODE_LIVE),
        "accessibility": _layer(codes, "accessibility_score", a, SOURCE_MODE_LIVE),
        "competition": _layer(codes, "commercial_density_score", c, SOURCE_MODE_LIVE),
        "cost": _layer(codes, "cost_pressure_score", k, SOURCE_MODE_LIVE),
    }


def test_four_layers_join_on_area_code() -> None:
    codes = ["13101", "13104", "13113"]
    fifty = [50, 50, 50]
    out = integrate_opportunity(_all_live(codes, fifty, fifty, fifty, fifty))
    assert set(out["area_code"]) == set(codes)
    assert out["available_layer_count"].eq(4).all()
    assert out["missing_layer_count"].eq(0).all()


def test_demand_and_accessibility_are_positive() -> None:
    codes = ["13101", "13104"]
    # 13104 has higher demand and accessibility, everything else equal -> higher score.
    layers = _all_live(codes, d=[10, 90], a=[10, 90], c=[50, 50], k=[50, 50])
    out = integrate_opportunity(layers).set_index("area_code")
    assert out.loc["13104", "opportunity_score"] > out.loc["13101", "opportunity_score"]


def test_competition_and_cost_are_negative() -> None:
    codes = ["13101", "13104"]
    # 13104 has higher competition and cost pressure -> LOWER score.
    layers = _all_live(codes, d=[50, 50], a=[50, 50], c=[10, 90], k=[10, 90])
    out = integrate_opportunity(layers).set_index("area_code")
    assert out.loc["13104", "opportunity_score"] < out.loc["13101", "opportunity_score"]


def test_missing_layer_raises_uncertainty_penalty() -> None:
    codes = ["13101"]
    full = integrate_opportunity(_all_live(codes, [50], [50], [50], [50]))
    partial = integrate_opportunity(
        {
            "demand": _layer(codes, "demand_score", [50], SOURCE_MODE_LIVE),
            "accessibility": None,
            "competition": None,
            "cost": None,
        }
    )
    assert full["data_uncertainty_penalty"].iloc[0] == 0.0
    assert partial["data_uncertainty_penalty"].iloc[0] > 0.0
    assert partial["missing_layer_count"].iloc[0] == 3


def test_sample_fixture_is_not_treated_as_real() -> None:
    codes = ["13101", "13104"]
    layers = {
        "demand": _layer(codes, "demand_score", [50, 60], SOURCE_MODE_SAMPLE),
        "accessibility": _layer(codes, "accessibility_score", [50, 60], SOURCE_MODE_SAMPLE),
        "competition": _layer(codes, "commercial_density_score", [50, 60], SOURCE_MODE_SAMPLE),
        "cost": _layer(codes, "cost_pressure_score", [50, 60], SOURCE_MODE_SAMPLE),
    }
    out = integrate_opportunity(layers, source_mode=SOURCE_MODE_SAMPLE)
    assert classify_opportunity(out) == "sample_fixture"
    assert classify_opportunity(out) != "live_public"
    # Sample layers contribute no live layers -> confidence is Low for every ward.
    assert (out["confidence_label"] == "Low").all()
    assert out["live_layer_count"].eq(0).all()
    assert count_live_layers(layers) == 0


def test_confidence_label_high_medium_low() -> None:
    codes = ["13101"]
    live = lambda col, v: _layer(codes, col, [v], SOURCE_MODE_LIVE)  # noqa: E731

    high = integrate_opportunity(
        {"demand": live("demand_score", 50), "accessibility": live("accessibility_score", 50),
         "competition": live("commercial_density_score", 50), "cost": None}
    )
    assert high["confidence_label"].iloc[0] == "High"  # 3 live

    medium = integrate_opportunity(
        {"demand": live("demand_score", 50), "accessibility": live("accessibility_score", 50),
         "competition": None, "cost": None}
    )
    assert medium["confidence_label"].iloc[0] == "Medium"  # 2 live

    low = integrate_opportunity(
        {"demand": live("demand_score", 50), "accessibility": None,
         "competition": None, "cost": None}
    )
    assert low["confidence_label"].iloc[0] == "Low"  # 1 live


def test_scores_are_finite() -> None:
    codes = ["13101", "13104", "13113"]
    out = integrate_opportunity(
        _all_live(codes, [0, 100, 50], [100, 0, 50], [0, 100, 50], [100, 0, 50])
    )
    assert np.isfinite(out["opportunity_score"]).all()
    assert not out["opportunity_score"].isna().any()


def test_weights_can_change_ranking() -> None:
    codes = ["13101", "13104"]
    # 13101: high demand, high cost. 13104: low demand, low cost.
    layers = _all_live(codes, d=[90, 40], a=[50, 50], c=[50, 50], k=[90, 10])

    demand_heavy = integrate_opportunity(
        layers, weights=OpportunityWeights(demand=2.0, cost=0.1)
    )
    cost_heavy = integrate_opportunity(
        layers, weights=OpportunityWeights(demand=0.5, cost=2.0)
    )
    assert demand_heavy.iloc[0]["area_code"] == "13101"  # demand wins
    assert cost_heavy.iloc[0]["area_code"] == "13104"   # cost penalty flips it


def test_layer_sign_metadata_drives_score() -> None:
    # Each layer's +/- direction must come from its _LAYER_SPECS is_positive flag,
    # not a hardcoded formula. Vary one layer at a time; all others held neutral.
    codes = ["13101", "13104"]
    score_cols = {
        "demand": "demand_score",
        "accessibility": "accessibility_score",
        "competition": "commercial_density_score",
        "cost": "cost_pressure_score",
    }
    for key, _src, _dst, _weight_attr, is_positive in _LAYER_SPECS:
        layers = {}
        for layer_key, col in score_cols.items():
            values = [10, 90] if layer_key == key else [50, 50]  # 13104 higher in `key`
            layers[layer_key] = _layer(codes, col, values, SOURCE_MODE_LIVE)
        out = integrate_opportunity(layers).set_index("area_code")
        higher = out.loc["13104", "opportunity_score"]
        lower = out.loc["13101", "opportunity_score"]
        if is_positive:
            assert higher > lower, f"{key} should be a positive factor"
        else:
            assert higher < lower, f"{key} should be a negative factor"


def _daytime(codes: list[str], scores: list[float], mode: str = SOURCE_MODE_LIVE) -> pd.DataFrame:
    return pd.DataFrame(
        {"area_code": codes, "daytime_activity_score": scores, "source_mode": [mode] * len(codes)}
    )


def test_daytime_default_weight_preserves_baseline() -> None:
    # Adding a daytime layer at the default weight (0) must not change the score,
    # confidence, or coverage counts vs. a 4-layer run.
    codes = ["13101", "13104"]
    layers = _all_live(codes, d=[10, 90], a=[50, 50], c=[50, 50], k=[50, 50])
    baseline = integrate_opportunity(layers).set_index("area_code")
    with_daytime = integrate_opportunity(
        layers, daytime_layer=_daytime(codes, [90, 10])
    ).set_index("area_code")

    assert with_daytime["opportunity_score"].equals(baseline["opportunity_score"])
    assert with_daytime["confidence_label"].equals(baseline["confidence_label"])
    assert with_daytime["live_layer_count"].equals(baseline["live_layer_count"])
    assert with_daytime["missing_layer_count"].equals(baseline["missing_layer_count"])


def test_daytime_weight_can_reorder_within_demand_axis() -> None:
    # Two wards equal on everything except daytime activity: 13101 has far higher daytime
    # activity. With a positive daytime weight it must outrank 13104.
    codes = ["13101", "13104"]
    layers = _all_live(codes, d=[50, 50], a=[50, 50], c=[50, 50], k=[50, 50])
    daytime = _daytime(codes, [100, 0])

    flat = integrate_opportunity(layers, daytime_layer=daytime).set_index("area_code")
    weighted = integrate_opportunity(
        layers, weights=OpportunityWeights(daytime=1.0), daytime_layer=daytime
    ).set_index("area_code")

    # At weight 0 the two are tied; raising the daytime weight lifts the high-daytime ward.
    assert flat.loc["13101", "opportunity_score"] == flat.loc["13104", "opportunity_score"]
    assert weighted.loc["13101", "opportunity_score"] > weighted.loc["13104", "opportunity_score"]


def test_daytime_does_not_change_coverage_or_confidence() -> None:
    # Daytime overlaps the Demand axis, so it must never count as a 5th coverage layer.
    codes = ["13101"]
    layers = {
        "demand": _layer(codes, "demand_score", [50], SOURCE_MODE_LIVE),
        "accessibility": None,
        "competition": None,
        "cost": None,
    }
    out = integrate_opportunity(
        layers, weights=OpportunityWeights(daytime=1.0), daytime_layer=_daytime(codes, [100])
    )
    # Still only 1 live core layer -> Low; daytime did not inflate the count.
    assert out["live_layer_count"].iloc[0] == 1
    assert out["available_layer_count"].iloc[0] == 1
    assert out["confidence_label"].iloc[0] == "Low"


def test_daytime_scores_stay_finite() -> None:
    codes = ["13101", "13104"]
    layers = _all_live(codes, d=[0, 100], a=[50, 50], c=[50, 50], k=[50, 50])
    out = integrate_opportunity(
        layers, weights=OpportunityWeights(daytime=2.0), daytime_layer=_daytime(codes, [100, 0])
    )
    assert np.isfinite(out["opportunity_score"]).all()
    assert not out["opportunity_score"].isna().any()


def test_empty_when_no_layers() -> None:
    out = integrate_opportunity(
        {"demand": None, "accessibility": None, "competition": None, "cost": None}
    )
    assert out.empty
    assert "opportunity_score" in out.columns


def test_default_weights_exist() -> None:
    assert isinstance(DEFAULT_WEIGHTS, OpportunityWeights)
