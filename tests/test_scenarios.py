"""Unit tests for the Opportunity scenario presets."""

from __future__ import annotations

import pytest

from tokyo_market_intel.ingestion.opportunity import DEFAULT_WEIGHTS, OpportunityWeights
from tokyo_market_intel.scenarios import (
    CUSTOM_SCENARIO,
    SCENARIO_DESCRIPTIONS,
    SCENARIO_ORDER,
    SCENARIO_PRESETS,
    get_scenario_weights,
)


def test_residential_baseline_matches_default_weights() -> None:
    # The residential baseline must equal the memo baseline (DEFAULT_WEIGHTS), so selecting
    # it leaves the documented ranking unchanged.
    assert get_scenario_weights("Residential baseline") == DEFAULT_WEIGHTS
    assert get_scenario_weights("Residential baseline").daytime == 0.0


def test_daytime_activity_weights_daytime() -> None:
    w = get_scenario_weights("Daytime activity")
    assert w.daytime > 0.0
    # Trades some resident demand weight for daytime presence.
    assert w.demand < DEFAULT_WEIGHTS.demand


def test_cost_sensitive_raises_cost_weight() -> None:
    w = get_scenario_weights("Cost-sensitive")
    assert w.cost > DEFAULT_WEIGHTS.cost
    assert w.daytime == 0.0


def test_all_presets_are_opportunity_weights() -> None:
    assert all(isinstance(w, OpportunityWeights) for w in SCENARIO_PRESETS.values())


def test_custom_is_in_order_but_not_a_preset() -> None:
    # Custom means "use the manual sliders" — it has no fixed weights.
    assert CUSTOM_SCENARIO in SCENARIO_ORDER
    assert CUSTOM_SCENARIO not in SCENARIO_PRESETS
    assert SCENARIO_ORDER[-1] == CUSTOM_SCENARIO


def test_every_selectable_scenario_has_a_description() -> None:
    for name in SCENARIO_ORDER:
        assert name in SCENARIO_DESCRIPTIONS and SCENARIO_DESCRIPTIONS[name]


def test_get_scenario_weights_rejects_unknown_and_custom() -> None:
    with pytest.raises(KeyError):
        get_scenario_weights("nonsense")
    with pytest.raises(KeyError):
        get_scenario_weights(CUSTOM_SCENARIO)
