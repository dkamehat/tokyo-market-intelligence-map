from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from tokyo_market_intel import ScoreWeights, compute_opportunity_scores
from tokyo_market_intel.ingestion.estat_daytime import classify_daytime_layer
from tokyo_market_intel.ingestion.estat_population import classify_demand_layer
from tokyo_market_intel.ingestion.mlit_accessibility import classify_accessibility_layer
from tokyo_market_intel.ingestion.mlit_cost import classify_cost_layer
from tokyo_market_intel.ingestion.opportunity import (
    CAVEAT,
    MIN_LIVE_LAYERS_FOR_REAL,
    SOURCE_MODE_LIVE,
    SOURCE_MODE_SAMPLE,
    OpportunityWeights,
    count_live_layers,
    integrate_opportunity,
)
from tokyo_market_intel.ingestion.osm_competition import classify_competition_layer
from tokyo_market_intel.scenarios import (
    CUSTOM_SCENARIO,
    SCENARIO_DESCRIPTIONS,
    SCENARIO_ORDER,
    get_scenario_weights,
)

# Public-data-backed layers. These are the LIVE files. Sample runs write separate
# *_sample.csv files the dashboard does not load, and provenance is verified via
# source_mode regardless of filename.
_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_PROCESSED = _DATA_DIR / "processed"
ESTAT_DEMAND_PATH = _PROCESSED / "estat_demand_tokyo23.csv"
ESTAT_DAYTIME_PATH = _PROCESSED / "estat_daytime_tokyo23.csv"
OSM_COMPETITION_PATH = _PROCESSED / "osm_competition_tokyo23.csv"
MLIT_ACCESS_PATH = _PROCESSED / "mlit_accessibility_tokyo23.csv"
MLIT_COST_PATH = _PROCESSED / "mlit_cost_tokyo23.csv"

# Sample-fixture layer files, used only for the clearly-labeled demo integration.
_SAMPLE_LAYER_PATHS = {
    "demand": _PROCESSED / "estat_demand_tokyo23_sample.csv",
    "accessibility": _PROCESSED / "mlit_accessibility_tokyo23_sample.csv",
    "competition": _PROCESSED / "osm_competition_tokyo23_sample.csv",
    "cost": _PROCESSED / "mlit_cost_tokyo23_sample.csv",
}
# Daytime activity is a Demand-axis refinement, passed separately (not a coverage layer).
_DAYTIME_SAMPLE_PATH = _PROCESSED / "estat_daytime_tokyo23_sample.csv"

# Columns shown in the opportunity ranking (caveat is shown once as a caption).
_OPPORTUNITY_DISPLAY_COLS = [
    "area",
    "area_code",
    "opportunity_score",
    "confidence_label",
    "demand_score",
    "daytime_activity_score",
    "accessibility_score",
    "competition_pressure",
    "cost_pressure",
    "data_uncertainty_penalty",
    "live_layer_count",
    "missing_layer_count",
]

# Remaining layers are still synthetic placeholders.
_SYNTH = "Synthetic placeholder"
OTHER_LAYER_STATUS = [
    {"Metric layer": "Growth", "Status": _SYNTH, "Source": "not yet implemented"},
    {"Metric layer": "Uncertainty", "Status": _SYNTH, "Source": "not yet implemented"},
]

# Status text by provenance class for the public-data-backed layers.
DEMAND_STATUS_BY_CLASS = {
    "missing": "Public-data-backed (not generated yet)",
    "live_public": "Public-data-backed (e-Stat)",
    "sample_fixture": "Sample fixture — NOT REAL DATA",
    "unknown": "Unverified provenance — treat as not real",
}
DAYTIME_STATUS_BY_CLASS = {
    "missing": "Public-data-backed (not generated yet)",
    "live_public": "Public-data-backed (e-Stat daytime)",
    "sample_fixture": "Sample fixture — NOT REAL DATA",
    "unknown": "Unverified provenance — treat as not real",
}
COMPETITION_STATUS_BY_CLASS = {
    "missing": "Public-data-backed (not generated yet)",
    "live_public": "Public-data-backed (OSM/Overpass)",
    "sample_fixture": "Sample fixture — NOT REAL DATA",
    "unknown": "Unverified provenance — treat as not real",
}
ACCESS_STATUS_BY_CLASS = {
    "missing": "Public-data-backed (live needs GIS opt-in)",
    "live_public": "Public-data-backed (MLIT N02)",
    "sample_fixture": "Sample fixture — NOT REAL DATA",
    "unknown": "Unverified provenance — treat as not real",
}
COST_STATUS_BY_CLASS = {
    "missing": "Public-data-backed (needs L01 download)",
    "live_public": "Public-data-backed (MLIT L01)",
    "sample_fixture": "Sample fixture — NOT REAL DATA",
    "unknown": "Unverified provenance — treat as not real",
}


@st.cache_data
def load_demo_data() -> pd.DataFrame:
    """Return synthetic Tokyo-like area data for MVP UI development.

    This is intentionally not real public data. It exists to validate dashboard
    flow before ingestion work starts.
    """

    return pd.DataFrame(
        {
            "area": [
                "Kitasenju",
                "Nakano",
                "Kinshicho",
                "Kamata",
                "Sangenjaya",
                "Machida",
                "Akabane",
                "Toyosu",
            ],
            "demand_score": [86, 78, 82, 74, 76, 70, 72, 68],
            "accessibility_score": [88, 84, 86, 80, 72, 76, 82, 70],
            "growth_score": [64, 58, 62, 54, 46, 52, 50, 74],
            "competition_pressure": [72, 68, 74, 58, 76, 54, 56, 48],
            "cost_pressure": [54, 62, 58, 48, 76, 44, 46, 82],
            "uncertainty_penalty": [28, 30, 34, 42, 38, 46, 40, 52],
            "plain_english_caveat": [
                "Strong hub, but competition is high.",
                "Balanced area with high accessibility.",
                "High activity proxy, but saturation risk is high.",
                "Cost pressure is relatively manageable.",
                "Attractive demand, but cost and competition are heavy.",
                "Lower centrality, but cost pressure is lighter.",
                "Good accessibility with moderate competition.",
                "Growth-like signal is high, but cost pressure is heavy.",
            ],
        }
    )


def build_weights() -> ScoreWeights:
    st.sidebar.header("Scenario weights")
    st.sidebar.caption("Change assumptions and watch the ranking move.")

    preset = st.sidebar.selectbox(
        "Scenario preset",
        ["Balanced", "Growth-seeking", "Cost-sensitive", "Operations-access"],
    )

    presets = {
        "Balanced": ScoreWeights(),
        "Growth-seeking": ScoreWeights(
            demand=1.4,
            accessibility=0.9,
            growth=1.1,
            competition=0.5,
            cost=0.4,
            uncertainty=0.8,
        ),
        "Cost-sensitive": ScoreWeights(
            demand=0.9,
            accessibility=0.8,
            growth=0.5,
            competition=1.0,
            cost=1.2,
            uncertainty=0.9,
        ),
        "Operations-access": ScoreWeights(
            demand=0.9,
            accessibility=1.5,
            growth=0.4,
            competition=0.6,
            cost=0.5,
            uncertainty=0.8,
        ),
    }
    selected = presets[preset]

    return ScoreWeights(
        demand=st.sidebar.slider("Demand", 0.0, 2.0, selected.demand, 0.1),
        accessibility=st.sidebar.slider(
            "Accessibility",
            0.0,
            2.0,
            selected.accessibility,
            0.1,
        ),
        growth=st.sidebar.slider("Growth", 0.0, 2.0, selected.growth, 0.1),
        competition=st.sidebar.slider(
            "Competition penalty",
            0.0,
            2.0,
            selected.competition,
            0.1,
        ),
        cost=st.sidebar.slider("Cost penalty", 0.0, 2.0, selected.cost, 0.1),
        uncertainty=st.sidebar.slider(
            "Uncertainty penalty",
            0.0,
            2.0,
            selected.uncertainty,
            0.1,
        ),
    )


@st.cache_data
def load_estat_demand_layer() -> pd.DataFrame | None:
    """Load the demand layer file if it has been generated.

    Returns ``None`` when the file is absent (e.g. a fresh clone, or no ingestion run
    yet), so the synthetic MVP keeps working without it. Provenance is NOT inferred
    from the filename — callers must check ``source_mode`` via ``classify_demand_layer``.
    """

    if not ESTAT_DEMAND_PATH.exists():
        return None
    return pd.read_csv(ESTAT_DEMAND_PATH, dtype={"area_code": str})


@st.cache_data
def load_osm_competition_layer() -> pd.DataFrame | None:
    """Load the OSM competition layer file if it has been generated.

    Returns ``None`` when absent. Provenance is verified via ``source_mode``
    (``classify_competition_layer``), not the filename.
    """

    if not OSM_COMPETITION_PATH.exists():
        return None
    return pd.read_csv(OSM_COMPETITION_PATH, dtype={"area_code": str})


@st.cache_data
def load_mlit_accessibility_layer() -> pd.DataFrame | None:
    """Load the MLIT accessibility layer file if it has been generated.

    Returns ``None`` when absent. Provenance is verified via ``source_mode``
    (``classify_accessibility_layer``), not the filename.
    """

    if not MLIT_ACCESS_PATH.exists():
        return None
    return pd.read_csv(MLIT_ACCESS_PATH, dtype={"area_code": str})


@st.cache_data
def load_mlit_cost_layer() -> pd.DataFrame | None:
    """Load the MLIT cost layer file if it has been generated.

    Returns ``None`` when absent. Provenance is verified via ``source_mode``
    (``classify_cost_layer``), not the filename.
    """

    if not MLIT_COST_PATH.exists():
        return None
    return pd.read_csv(MLIT_COST_PATH, dtype={"area_code": str})


@st.cache_data
def load_estat_daytime_layer() -> pd.DataFrame | None:
    """Load the e-Stat daytime-activity layer file if it has been generated.

    Returns ``None`` when absent. Provenance is verified via ``source_mode``
    (``classify_daytime_layer``), not the filename.
    """

    if not ESTAT_DAYTIME_PATH.exists():
        return None
    return pd.read_csv(ESTAT_DAYTIME_PATH, dtype={"area_code": str})


def render_data_status(
    demand_class: str,
    competition_class: str,
    accessibility_class: str,
    cost_class: str,
) -> None:
    """Show, unambiguously, which layers are real public data vs synthetic."""

    st.subheader("Data status — real vs synthetic")
    demand_row = {
        "Metric layer": "Demand",
        "Status": DEMAND_STATUS_BY_CLASS[demand_class],
        "Source": "e-Stat Population Census" if demand_class == "live_public" else "—",
    }
    competition_row = {
        "Metric layer": "Competition",
        "Status": COMPETITION_STATUS_BY_CLASS[competition_class],
        "Source": "OSM convenience stores" if competition_class == "live_public" else "—",
    }
    accessibility_row = {
        "Metric layer": "Accessibility",
        "Status": ACCESS_STATUS_BY_CLASS[accessibility_class],
        "Source": "MLIT N02 stations" if accessibility_class == "live_public" else "—",
    }
    cost_row = {
        "Metric layer": "Cost",
        "Status": COST_STATUS_BY_CLASS[cost_class],
        "Source": "MLIT L01 land price" if cost_class == "live_public" else "—",
    }
    status = pd.DataFrame(
        [demand_row, competition_row, accessibility_row, cost_row, *OTHER_LAYER_STATUS]
    )
    st.dataframe(status, use_container_width=True, hide_index=True)
    st.caption(
        "A layer is shown as REAL only when its rows are labeled source_mode="
        "'live_public'. Sample-fixture output is never treated as real."
    )


def render_public_demand_layer(demand_layer: pd.DataFrame | None, demand_class: str) -> None:
    """Render the demand layer according to its verified provenance."""

    columns = ["area", "area_code", "population", "demand_score", "source_mode", "data_basis"]

    if demand_class == "missing":
        st.subheader("Demand layer (e-Stat)")
        st.warning(
            "Not generated yet. Run the ingestion script to create it:\n\n"
            "`python scripts/ingest_estat_population.py --cat-filter @cat01=000`\n\n"
            "Without ESTAT_APP_ID it runs in **sample mode** (schema fixture → a "
            "separate `*_sample.csv`, not a real finding). With ESTAT_APP_ID + "
            "ESTAT_STATS_DATA_ID it pulls real data into the live file."
        )
        return

    available = [column for column in columns if column in demand_layer.columns]

    if demand_class == "live_public":
        st.subheader("Public-data-backed demand layer (e-Stat) — REAL")
        st.success(
            "Tokyo 23 wards ranked by population as a demographic demand proxy. A "
            "structural proxy only — not income, purchasing power, or actual demand."
        )
        st.dataframe(demand_layer[available], use_container_width=True, hide_index=True)
        return

    if demand_class == "sample_fixture":
        st.subheader("Demand layer — Sample fixture — NOT REAL DATA")
        st.error(
            "This file was produced in SAMPLE mode from a schema fixture. The numbers "
            "are illustrative only and must NOT be read as a real Tokyo finding. "
            "Generate the live layer with ESTAT_APP_ID to replace it."
        )
        st.dataframe(demand_layer[available], use_container_width=True, hide_index=True)
        return

    # unknown / mixed provenance
    st.subheader("Demand layer — unverified provenance")
    st.error(
        "The demand file lacks a recognized source_mode and is treated as NOT real. "
        "Regenerate it with the ingestion script."
    )
    st.dataframe(demand_layer[available], use_container_width=True, hide_index=True)


def render_daytime_layer(layer: pd.DataFrame | None, daytime_class: str) -> None:
    """Render the e-Stat daytime-activity layer (Demand-axis refinement)."""

    columns = [
        "area",
        "area_code",
        "daytime_population",
        "daytime_activity_score",
        "resident_population_reference",
        "daytime_to_resident_ratio",
        "source_mode",
        "data_basis",
    ]

    if daytime_class == "missing":
        st.subheader("Daytime activity layer (e-Stat 2020 Census)")
        st.warning(
            "Not generated yet. Run:\n\n"
            "`python scripts/ingest_estat_daytime.py`\n\n"
            "Without ESTAT_APP_ID it runs in **sample mode** (schema fixture → a separate "
            "`*_sample.csv`). With ESTAT_APP_ID + ESTAT_DAYTIME_STATS_DATA_ID it pulls the "
            "real daytime-population table. Daytime population is a daytime-activity proxy "
            "— not demand, sales, or revenue."
        )
        return

    available = [column for column in columns if column in layer.columns]

    if daytime_class == "live_public":
        st.subheader("Public-data-backed daytime activity layer (e-Stat) — REAL")
        st.success(
            "Tokyo 23 wards by daytime population (place of work/schooling) as a daytime-"
            "activity proxy. Complements the resident Demand layer; raise the Daytime "
            "weight to weight commuter/daytime presence. Not demand, sales, or revenue."
        )
        st.dataframe(layer[available], use_container_width=True, hide_index=True)
        return

    if daytime_class == "sample_fixture":
        st.subheader("Daytime activity layer — Sample fixture — NOT REAL DATA")
        st.error(
            "Produced in SAMPLE mode from a schema fixture — illustrative only, NOT a real "
            "Tokyo finding. Generate the live layer with ESTAT_APP_ID + "
            "ESTAT_DAYTIME_STATS_DATA_ID to replace it."
        )
        st.dataframe(layer[available], use_container_width=True, hide_index=True)
        return

    st.subheader("Daytime activity layer — unverified provenance")
    st.error(
        "The daytime file lacks a recognized source_mode and is treated as NOT real. "
        "Regenerate it with the ingestion script."
    )
    st.dataframe(layer[available], use_container_width=True, hide_index=True)


def render_competition_layer(layer: pd.DataFrame | None, competition_class: str) -> None:
    """Render the OSM competition-density layer according to its provenance."""

    columns = [
        "area",
        "area_code",
        "poi_count",
        "commercial_density_score",
        "poi_per_10k",
        "source_mode",
        "data_basis",
        "attribution",
    ]

    if competition_class == "missing":
        st.subheader("Competition / commercial-density layer (OSM)")
        st.warning(
            "Not generated yet. Run the ingestion script to create it:\n\n"
            "`python scripts/ingest_osm_competition.py`\n\n"
            "Default (sample) mode uses a schema fixture → a separate `*_sample.csv`, "
            "not a real finding. Use `--mode live` to query real OSM data."
        )
        return

    available = [column for column in columns if column in layer.columns]

    if competition_class == "live_public":
        st.subheader("Public-data-backed competition layer (OSM) — REAL")
        st.success(
            "Tokyo 23 wards by `shop=convenience` density — a commercial-density / "
            "competition proxy only, NOT demand, sales, or revenue. "
            "© OpenStreetMap contributors (ODbL)."
        )
        st.dataframe(layer[available], use_container_width=True, hide_index=True)
        return

    if competition_class == "sample_fixture":
        st.subheader("Competition layer — Sample fixture — NOT REAL DATA")
        st.error(
            "Produced in SAMPLE mode from a schema fixture. Counts are illustrative "
            "only and must NOT be read as a real Tokyo finding. Run `--mode live` to "
            "query real OSM data. © OpenStreetMap contributors (ODbL)."
        )
        st.dataframe(layer[available], use_container_width=True, hide_index=True)
        return

    # unknown / mixed provenance
    st.subheader("Competition layer — unverified provenance")
    st.error(
        "The competition file lacks a recognized source_mode and is treated as NOT "
        "real. Regenerate it with the ingestion script."
    )
    st.dataframe(layer[available], use_container_width=True, hide_index=True)


def render_accessibility_layer(layer: pd.DataFrame | None, accessibility_class: str) -> None:
    """Render the MLIT accessibility layer according to its provenance."""

    columns = [
        "area",
        "area_code",
        "station_count",
        "accessibility_score",
        "station_count_per_10k",
        "source_mode",
        "data_basis",
        "attribution",
    ]

    if accessibility_class == "missing":
        st.subheader("Accessibility layer (MLIT N02 stations)")
        st.warning(
            "No live layer yet. Sample mode works now:\n\n"
            "`python scripts/ingest_mlit_accessibility.py`\n\n"
            "Live N02 ingestion needs a deferred GIS step (point-in-polygon vs. ward "
            "boundaries) — opt into `pip install -e \".[geo]\"` in a follow-up."
        )
        return

    available = [column for column in columns if column in layer.columns]

    if accessibility_class == "live_public":
        st.subheader("Public-data-backed accessibility layer (MLIT N02) — REAL")
        st.success(
            "Tokyo 23 wards by railway station count — a station-access proxy only, "
            "NOT demand or willingness to buy. "
            "出典：国土数値情報（鉄道データ N02）（国土交通省）."
        )
        st.dataframe(layer[available], use_container_width=True, hide_index=True)
        return

    if accessibility_class == "sample_fixture":
        st.subheader("Accessibility layer — Sample fixture — NOT REAL DATA")
        st.error(
            "Produced in SAMPLE mode from a schema fixture. Counts are illustrative "
            "only and must NOT be read as a real Tokyo finding. "
            "出典：国土数値情報（鉄道データ N02）（国土交通省）."
        )
        st.dataframe(layer[available], use_container_width=True, hide_index=True)
        return

    # unknown / mixed provenance
    st.subheader("Accessibility layer — unverified provenance")
    st.error(
        "The accessibility file lacks a recognized source_mode and is treated as NOT "
        "real. Regenerate it with the ingestion script."
    )
    st.dataframe(layer[available], use_container_width=True, hide_index=True)


def render_cost_layer(layer: pd.DataFrame | None, cost_class: str) -> None:
    """Render the MLIT cost-pressure (land price) layer according to its provenance."""

    columns = [
        "area",
        "area_code",
        "land_price_median",
        "cost_pressure_score",
        "land_price_mean",
        "observation_count",
        "source_mode",
        "data_basis",
        "attribution",
    ]
    proxy_note = (
        "Cost pressure proxy from published land price (円/m²) — NOT store rent, "
        "operating cost, or profit margin. Higher = more cost pressure (a negative "
        "factor in opportunity). 出典：国土数値情報（地価公示データ L01）（国土交通省）."
    )

    if cost_class == "missing":
        st.subheader("Cost pressure layer (MLIT L01 land price)")
        st.warning(
            "No live layer yet. Sample mode works now:\n\n"
            "`python scripts/ingest_mlit_cost.py`\n\n"
            "Live mode is GIS-free (L01 has the municipality code) — download the L01 "
            "Tokyo GeoJSON and pass it: `--mode live --geojson <file>`."
        )
        return

    available = [column for column in columns if column in layer.columns]

    if cost_class == "live_public":
        st.subheader("Public-data-backed cost pressure layer (MLIT L01) — REAL")
        st.success(proxy_note)
        st.dataframe(layer[available], use_container_width=True, hide_index=True)
        return

    if cost_class == "sample_fixture":
        st.subheader("Cost pressure layer — Sample fixture — NOT REAL DATA")
        st.error(
            "Produced in SAMPLE mode from a schema fixture. Figures are illustrative "
            "only and must NOT be read as a real Tokyo finding. " + proxy_note
        )
        st.dataframe(layer[available], use_container_width=True, hide_index=True)
        return

    # unknown / mixed provenance
    st.subheader("Cost pressure layer — unverified provenance")
    st.error(
        "The cost file lacks a recognized source_mode and is treated as NOT real. "
        "Regenerate it with the ingestion script."
    )
    st.dataframe(layer[available], use_container_width=True, hide_index=True)


def build_opportunity_weights() -> tuple[str, OpportunityWeights]:
    """Sidebar scenario preset + weights. Returns ``(scenario_name, weights)``.

    A scenario preset is a decision lens (a named weight bundle), not data truth — it never
    changes the underlying data, provenance, or confidence. ``Custom`` exposes manual sliders.
    """

    st.sidebar.header("Opportunity scenario")
    st.sidebar.caption(
        "A scenario is a decision lens (how signals are weighted), not a change to the data "
        "or its confidence. Daytime population is a daytime-activity proxy, not demand/sales."
    )
    scenario = st.sidebar.selectbox("Scenario preset", SCENARIO_ORDER, index=0)
    st.sidebar.caption(SCENARIO_DESCRIPTIONS.get(scenario, ""))

    if scenario != CUSTOM_SCENARIO:
        weights = get_scenario_weights(scenario)
        st.sidebar.caption(
            f"Weights — demand {weights.demand}, daytime {weights.daytime}, accessibility "
            f"{weights.accessibility}, competition {weights.competition}, cost {weights.cost}, "
            f"uncertainty {weights.uncertainty}. Choose **Custom** to adjust by hand."
        )
        return scenario, weights

    st.sidebar.caption("Custom — tune every weight below.")
    weights = OpportunityWeights(
        demand=st.sidebar.slider("Demand weight (resident)", 0.0, 2.0, 1.0, 0.1),
        daytime=st.sidebar.slider("Daytime activity weight", 0.0, 2.0, 0.0, 0.1),
        accessibility=st.sidebar.slider("Accessibility weight", 0.0, 2.0, 1.0, 0.1),
        competition=st.sidebar.slider("Competition penalty", 0.0, 2.0, 0.7, 0.1),
        cost=st.sidebar.slider("Cost penalty", 0.0, 2.0, 0.5, 0.1),
        uncertainty=st.sidebar.slider("Uncertainty penalty", 0.0, 2.0, 0.5, 0.1),
    )
    return CUSTOM_SCENARIO, weights


def _load_sample_layers() -> dict[str, pd.DataFrame | None]:
    layers: dict[str, pd.DataFrame | None] = {}
    for key, path in _SAMPLE_LAYER_PATHS.items():
        layers[key] = pd.read_csv(path, dtype={"area_code": str}) if path.exists() else None
    return layers


def render_opportunity(
    live_layers: dict[str, pd.DataFrame | None],
    weights: OpportunityWeights,
    daytime_live: pd.DataFrame | None = None,
    scenario_name: str = CUSTOM_SCENARIO,
) -> None:
    """Render the integrated Opportunity Score — REAL only with enough live layers."""

    st.header("Opportunity Score — public-data integrated")
    st.caption(CAVEAT)
    st.caption(
        f"**Scenario: {scenario_name}** — a decision lens (weight setting), not data truth. "
        "Provenance and per-ward confidence are unchanged by the scenario."
    )

    live_count = count_live_layers(live_layers)
    if live_count >= MIN_LIVE_LAYERS_FOR_REAL:
        opportunity = integrate_opportunity(
            live_layers,
            weights=weights,
            source_mode=SOURCE_MODE_LIVE,
            daytime_layer=daytime_live,
        )
        st.success(
            f"REAL — integrated from {live_count} live public-data layer(s). "
            "Screening only; confidence reflects how many layers are live per ward."
        )
        st.dataframe(
            opportunity[_OPPORTUNITY_DISPLAY_COLS],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.warning(
            f"Not enough live public-data layers for a REAL ranking "
            f"(have {live_count}, need ≥ {MIN_LIVE_LAYERS_FOR_REAL}). Generate live "
            "layers (e.g. e-Stat live, MLIT L01 live), then re-open. The sample/demo "
            "integration below shows the logic only."
        )

    sample_layers = _load_sample_layers()
    if any(layer is not None for layer in sample_layers.values()):
        with st.expander(
            "Sample / demo integration (NOT REAL — logic demonstration)",
            expanded=live_count < MIN_LIVE_LAYERS_FOR_REAL,
        ):
            daytime_sample = (
                pd.read_csv(_DAYTIME_SAMPLE_PATH, dtype={"area_code": str})
                if _DAYTIME_SAMPLE_PATH.exists()
                else None
            )
            demo = integrate_opportunity(
                sample_layers,
                weights=weights,
                source_mode=SOURCE_MODE_SAMPLE,
                daytime_layer=daytime_sample,
            )
            st.error(
                "DEMO from sample fixtures — NOT a real finding. Shown only to "
                "demonstrate the integration and confidence logic."
            )
            st.dataframe(
                demo[_OPPORTUNITY_DISPLAY_COLS],
                use_container_width=True,
                hide_index=True,
            )


def main() -> None:
    st.set_page_config(page_title="Tokyo Market Intelligence Map", layout="wide")

    st.title("Tokyo Market Intelligence Map")

    demand_layer = load_estat_demand_layer()
    demand_class = classify_demand_layer(demand_layer)
    daytime_layer = load_estat_daytime_layer()
    daytime_class = classify_daytime_layer(daytime_layer)
    competition_layer = load_osm_competition_layer()
    competition_class = classify_competition_layer(competition_layer)
    accessibility_layer = load_mlit_accessibility_layer()
    accessibility_class = classify_accessibility_layer(accessibility_layer)
    cost_layer = load_mlit_cost_layer()
    cost_class = classify_cost_layer(cost_layer)

    real_layers = [
        name
        for name, klass in (
            ("Demand", demand_class),
            ("Competition", competition_class),
            ("Accessibility", accessibility_class),
            ("Cost", cost_class),
        )
        if klass == "live_public"
    ]
    if real_layers:
        st.caption(
            f"Public-data integration in progress — REAL public-data layers: "
            f"{', '.join(real_layers)}. Remaining layers are synthetic."
        )
    else:
        st.caption(
            "Public-data integration in progress — no real public-data layer loaded "
            "yet; all displayed metrics are synthetic or sample data."
        )

    render_data_status(demand_class, competition_class, accessibility_class, cost_class)

    # Integrated opportunity score (REAL only when enough layers are live_public).
    live_layers = {
        "demand": demand_layer if demand_class == "live_public" else None,
        "accessibility": accessibility_layer if accessibility_class == "live_public" else None,
        "competition": competition_layer if competition_class == "live_public" else None,
        "cost": cost_layer if cost_class == "live_public" else None,
    }
    scenario_name, opportunity_weights = build_opportunity_weights()
    daytime_live = daytime_layer if daytime_class == "live_public" else None
    render_opportunity(
        live_layers, opportunity_weights, daytime_live=daytime_live, scenario_name=scenario_name
    )

    st.divider()
    st.subheader("Individual public-data layers")
    render_public_demand_layer(demand_layer, demand_class)
    render_daytime_layer(daytime_layer, daytime_class)
    render_competition_layer(competition_layer, competition_class)
    render_accessibility_layer(accessibility_layer, accessibility_class)
    render_cost_layer(cost_layer, cost_class)

    st.divider()
    st.header("Synthetic decision-flow prototype")
    st.info(
        "The ranking below uses SYNTHETIC data to validate the scenario/scoring flow. "
        "Do not interpret these rankings as real findings — only a Demand layer marked "
        "REAL above is backed by public data."
    )

    raw_df = load_demo_data()
    weights = build_weights()
    scored_df = compute_opportunity_scores(raw_df, weights)

    top = scored_df.iloc[0]

    col1, col2, col3 = st.columns(3)
    col1.metric("Top priority area", top["area"])
    col2.metric("Opportunity score", f"{top['opportunity_score']:.1f}")
    col3.metric("Confidence", top["confidence_label"])

    st.subheader("Area ranking")
    st.dataframe(
        scored_df[
            [
                "area",
                "opportunity_score",
                "confidence_label",
                "demand_score",
                "accessibility_score",
                "growth_score",
                "competition_pressure",
                "cost_pressure",
                "uncertainty_penalty",
                "plain_english_caveat",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Score breakdown")
    selected_area = st.selectbox("Select area", scored_df["area"].tolist())
    selected = scored_df.loc[scored_df["area"] == selected_area].iloc[0]

    breakdown = pd.DataFrame(
        {
            "metric": [
                "Demand",
                "Accessibility",
                "Growth",
                "Competition pressure",
                "Cost pressure",
                "Uncertainty penalty",
            ],
            "score": [
                selected["demand_score"],
                selected["accessibility_score"],
                selected["growth_score"],
                selected["competition_pressure"],
                selected["cost_pressure"],
                selected["uncertainty_penalty"],
            ],
        }
    )
    st.bar_chart(breakdown, x="metric", y="score")

    st.subheader("Decision caveat")
    st.write(selected["plain_english_caveat"])
    st.write(
        "Next step: replace synthetic metrics with official public data, then keep "
        "confidence and proxy-risk visible next to every recommendation."
    )


if __name__ == "__main__":
    main()
