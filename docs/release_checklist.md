# Portfolio Release Checklist

A pre-submission audit of the Tokyo Market Intelligence Map, so a reviewer (or the author)
can confirm at a glance what is ready, what is intentionally pending, and what must **not** be
overclaimed. Last audited: June 2026.

## What is ready

- **Three live public-data layers** (every row `source_mode = live_public`):
  - **Demand** — e-Stat 2020 Census resident population (ward grain).
  - **Daytime activity** — e-Stat 2020 Census 昼間人口 (Demand-axis refinement, default weight 0).
  - **Cost** — MLIT L01 2023 地価公示 land price (median, ward grain).
- **Integrated Opportunity Score** — REAL ranking at **Medium** confidence (2 of 4 coverage
  layers live), with a per-ward `data_uncertainty_penalty` and `confidence_label`.
- **Decision memo** (`decision_memo_tokyo.md`) — live-backed recommendation (Setagaya /
  Nerima / Ota top; central high-cost wards low), with evidence, scenario sensitivity, and
  limitations.
- **Scenario presets** — Residential baseline / Daytime activity / Cost-sensitive / Custom
  (decision lenses; provenance and confidence are unchanged by the choice).
- **Reproducibility** — `live_data_runbook.md` documents exact steps + observed results.
- **Engineering hygiene** — pure transforms with unit tests (111 passing), ruff clean, CI
  (ruff + pytest), provenance-stamped layers, secrets/generated data gitignored.

## What is intentionally pending (backlog, not gaps)

- **Competition (OSM/Overpass) live** — sample pipeline + 1-ward smoke test pass; the full
  live run is **pending** on public Overpass endpoint reliability (429/504). Retry off-peak.
- **Accessibility (MLIT N02) live** — **deferred** behind a GIS point-in-polygon step
  (GeoPandas), intentionally not added as a core dependency.
- **Growth layer** — not implemented (omitted, not faked).
- Reaching **High** confidence needs ≥ 3 live coverage layers (i.e. OSM or N02 live).

See the [Future Roadmap](future_roadmap.md) for the next development directions and the
recommended next sprint (OSM Competition live reliability).

## How to review the portfolio (reviewer path)

1. **README → Executive summary** (30 seconds): the result + confidence.
2. **`docs/decision_memo_tokyo.md`**: the recommendation, evidence, limitations.
3. **`docs/live_data_runbook.md`**: exact reproduction steps + observed results.
4. **`docs/metric_design.md`**: score definitions, the Opportunity formula, scenario presets.
5. **`app/streamlit_app.py`** / dashboard: real-vs-synthetic separation + scenario selector.

## How to reproduce live data

Credentials/config live in `.env` (never committed): `ESTAT_APP_ID`, `ESTAT_STATS_DATA_ID`
(resident table), `ESTAT_DAYTIME_STATS_DATA_ID` (daytime table). The statsDataId values are
**not displayed/committed** — pin them from the e-Stat catalog. Full steps + the verified
MLIT L01 download and the daytime category cell (`cat01=180`) are in `live_data_runbook.md`.

## What not to overclaim

This is **first-cut public-data screening**, a relative opportunity ranking. It is **NOT**:

- a revenue / sales forecast, an actual-demand prediction, or a profitability forecast;
- a final site-selection or investment recommendation;
- a claim of actual store rent, operating cost, or competitor performance.

Each metric is a labeled proxy (residential demand, daytime activity, commercial density,
cost pressure). Daytime population is a daytime-activity proxy; land price is a cost-pressure
proxy. Scenario presets are sensitivity analysis, not data truth.

## Known limitations

- Residential ≠ commercial opportunity — partly addressed by the tunable daytime layer; pick
  the resident/daytime blend deliberately per use case.
- The REAL ranking rests mainly on Demand (+) and Cost (−); Accessibility and Competition are
  neutral-filled at 50 and flagged via the uncertainty penalty (order unchanged, absolute
  score provisional).
- Min-max scores are relative to the 23-ward set; census data lags (5-year cycle); land-price
  points are sparse (`observation_count` exposes this).

## Public submission checklist

- [x] Dashboard runs locally; real-vs-synthetic clearly separated.
- [x] At least one public-data layer is live-verified (three are).
- [x] Metric definitions + data lineage documented; formulas live outside the UI.
- [x] Limitations and confidence stated next to the output.
- [x] Tests pass (`pytest`), lint clean (`ruff check .`), CI green.
- [x] No secrets, raw downloads, or generated tables committed (`.env`, `data/raw/`,
      `data/processed/` gitignored; no bare statsDataId in tracked files).
- [x] No overclaim language (revenue/demand/profitability/final-investment only ever appear
      as disclaimers).
- [x] Dashboard screenshots added to the README (`docs/assets/screenshots/`) — Residential
      baseline, Daytime activity, and the data-status table.
