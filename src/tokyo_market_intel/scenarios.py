"""Opportunity-Score scenario presets — decision lenses, not data truth.

A scenario preset is just a named bundle of :class:`OpportunityWeights`. It changes how the
public-data signals are *weighted* for a decision lens (e.g. residents vs. daytime/commuter
presence); it does **not** change the underlying data, its provenance, or the per-ward
confidence. This is sensitivity analysis, not a revenue/demand/profitability forecast.

Presets are defined here (pure, importable, testable) so the dashboard and the docs share one
source of truth. ``Custom`` is intentionally absent from :data:`SCENARIO_PRESETS` — it means
"use the manual sliders" and is handled by the UI.
"""

from __future__ import annotations

from .ingestion.opportunity import OpportunityWeights

# UI label for the manual-slider mode (no fixed weights).
CUSTOM_SCENARIO = "Custom"

# Named decision lenses -> weights. Residential baseline mirrors DEFAULT_WEIGHTS (the memo
# baseline). Daytime activity trades some resident weight for daytime presence. Cost-sensitive
# strengthens the cost-pressure penalty.
SCENARIO_PRESETS: dict[str, OpportunityWeights] = {
    "Residential baseline": OpportunityWeights(
        demand=1.0, daytime=0.0, accessibility=1.0, competition=0.7, cost=0.5, uncertainty=0.5
    ),
    "Daytime activity": OpportunityWeights(
        demand=0.7, daytime=1.0, accessibility=1.0, competition=0.7, cost=0.5, uncertainty=0.5
    ),
    "Cost-sensitive": OpportunityWeights(
        demand=1.0, daytime=0.0, accessibility=1.0, competition=0.7, cost=1.0, uncertainty=0.5
    ),
}

# One-line decision-lens description per scenario (shown in the dashboard + docs).
SCENARIO_DESCRIPTIONS: dict[str, str] = {
    "Residential baseline": (
        "Resident population + cost pressure — the current decision-memo baseline."
    ),
    "Daytime activity": (
        "Weights daytime / commuter presence; daytime-activity wards (Chiyoda, Minato, "
        "Chuo) rise relative to the residential baseline."
    ),
    "Cost-sensitive": (
        "Strengthens the land-cost-pressure penalty, pushing high-cost central wards down."
    ),
    CUSTOM_SCENARIO: "Set every weight by hand with the sliders below.",
}

# Display order for a selector (presets first, Custom last).
SCENARIO_ORDER: list[str] = [*SCENARIO_PRESETS.keys(), CUSTOM_SCENARIO]


def get_scenario_weights(name: str) -> OpportunityWeights:
    """Return the :class:`OpportunityWeights` for a named preset.

    Raises ``KeyError`` for unknown names and for ``Custom`` (which has no fixed weights —
    the caller supplies manual slider values instead).
    """

    if name not in SCENARIO_PRESETS:
        raise KeyError(
            f"Unknown scenario preset {name!r}. "
            f"Expected one of {sorted(SCENARIO_PRESETS)} (Custom uses manual sliders)."
        )
    return SCENARIO_PRESETS[name]
