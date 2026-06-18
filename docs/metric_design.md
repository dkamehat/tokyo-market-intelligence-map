# Metric Design

## Decision question

Where should a consumer business prioritize expansion, marketing, or micro-fulfillment investment in Tokyo?

## Score philosophy

The model should produce **decision support**, not a false claim of revenue prediction.

Public data is enough to rank first-cut opportunity, but not enough to estimate actual sales. Therefore, every output must include caveats and confidence.

## Core formula

```text
Opportunity Score
= Demand Score
+ Accessibility Score
+ Growth Score
- Competition Pressure
- Cost Pressure
- Data Uncertainty Penalty
```

In implementation, use weighted normalized scores:

```text
opportunity_score =
  w_demand * demand_score
+ w_accessibility * accessibility_score
+ w_growth * growth_score
- w_competition * competition_pressure
- w_cost * cost_pressure
- w_uncertainty * uncertainty_penalty
```

Weights are scenario parameters, not fixed truth.

## Metric groups

| Group | Intended meaning | Example public proxies | Key risk |
|---|---|---|---|
| Demand | Potential customer base or activity | population, households, daytime population, age structure | Public data does not equal actual demand |
| Accessibility | Ease of reaching / serving the area | station density, distance to station, roads | Access does not equal willingness to buy |
| Growth | Whether the area is becoming more attractive | population trend, land price trend, facility growth | Lagging indicators |
| Competition | Market saturation / pressure | POI density by category | OSM coverage can be uneven |
| Cost | Operating or investment pressure | land price, rent proxy | land price is not actual store rent |
| Uncertainty | How much to discount weak evidence | missingness, freshness, proxy risk | Hard to calibrate without internal data |

## Demand Score — current implementation (v1, e-Stat)

The first public-data-backed metric. Status: **implemented for Tokyo 23 wards**.

- **Definition (current):** `demand_score` = min-max scaling (0..100) of total
  population per ward, from the e-Stat Population Census. Higher population → higher
  demand-proxy score, relative to the other 22 wards.
- **Grain:** Tokyo 23 special wards (区), keyed by the 5-digit municipality code.
- **Source / transform:** `src/tokyo_market_intel/sources/estat.py` (API access) and
  `src/tokyo_market_intel/ingestion/estat_population.py` (pure transform). See
  `docs/data_sources.md` for the exact table.
- **Provenance (`source_mode`):** every demand row is labeled `live_public` (real
  e-Stat data) or `sample_fixture` (schema fixture, **not** a real finding). Sample
  mode writes a separate `*_sample.csv` and is never displayed as real. The default is
  the conservative `sample_fixture`, so real data must be requested explicitly.

### What this Demand Score can and cannot say

- **Can say:** relative residential population scale across wards — a *demographic /
  household-structure demand proxy*.
- **Cannot say:** income, purchasing power, spending, or actual demand. Daytime/working
  population, age mix, and household composition are **not yet** incorporated.

### Known limitations

- Total population is a coarse proxy: a high-population residential ward is not
  necessarily a high-commercial-opportunity ward (daytime population would refine this).
- Min-max scaling is relative to the current 23-ward set; adding/removing areas
  rescales every score.
- Census data lags real-time behavior (5-year cycle). The survey year should be carried
  as a freshness signal.

### Planned refinement

Blend total population with daytime population and a youth/working-age share, and
attach a freshness + coverage signal that feeds the Uncertainty penalty.

## Daytime Activity Score — current implementation (v1, e-Stat 昼間人口)

A **Demand-axis refinement**. Status: **implemented (sample + live verified)**.

- **Definition:** `daytime_activity_score` = min-max scaling (0..100) of per-ward **daytime
  population** (昼間人口) from the 2020 Census 従業地・通学地集計. Higher daytime presence →
  higher score.
- **Why it exists:** the resident-population Demand layer structurally penalizes daytime
  business districts. This layer exposes the resident-vs-daytime tension (e.g. Chiyoda's
  daytime population is ~13.5× its resident population; Setagaya is ~0.9×).
- **Source / transform:** `src/tokyo_market_intel/sources/estat_daytime.py` (metadata) +
  `ingestion/estat_daytime.py` (transform); e-Stat 従業地・通学地集計, daytime cell
  `cat01=180` (statsDataId pinned via `ESTAT_DAYTIME_STATS_DATA_ID`). See
  `docs/data_sources.md`.
- **How it enters the score:** a **positive Demand-axis term** with weight `w_daytime`,
  **default 0**, so the baseline ranking is unchanged. It is **not** a 5th coverage layer —
  it overlaps the resident Demand axis, so it never changes the confidence/uncertainty math.
  The "daytime activity" scenario raises `w_daytime` to weight commuter/daytime presence.
- **Provenance:** `live_public` vs `sample_fixture` (default conservative). Attribution:
  出典：令和2年国勢調査（総務省統計局）従業地・通学地集計.

### What it can and cannot say

- **Can say:** relative daytime/commuter presence across wards — a *daytime-activity proxy*.
- **Cannot say:** demand, sales, revenue, or profit. An optional `daytime_to_resident_ratio`
  is display-only (and approximate — it mixes two census tabulations differing by <1%), and
  is **not** fed into the score (a ratio would over-weight tiny-resident central wards — the
  reason the official 昼夜間人口比率 table is deferred).

## Competition / Commercial Density Score — current implementation (v1, OSM)

The second public-data-backed metric. Status: **implemented for Tokyo 23 wards**.

- **Definition (current):** `commercial_density_score` = min-max scaling (0..100) of the
  per-ward count of OpenStreetMap `shop=convenience` POIs. An optional `poi_per_10k`
  gives a per-capita density when the e-Stat population layer is available.
- **Grain / source / transform:** Tokyo 23 wards; `src/tokyo_market_intel/sources/`
  `overpass.py` (Overpass access) + `ingestion/osm_competition.py` (pure transform). See
  `docs/data_sources.md` for the selected tag and access/rate-limit details.
- **Provenance (`source_mode`):** `live_public` (real OSM) vs `sample_fixture` (NOT a
  real finding); default is the conservative `sample_fixture`. Every row carries
  `© OpenStreetMap contributors` (ODbL).

### What this score can and cannot say

- **Can say:** relative density of convenience retail across wards — a *commercial-
  density / competition proxy*.
- **Cannot say:** demand, sales, revenue, or store performance. High store density can
  mean either a strong commercial area or saturation, so this feeds **Competition
  pressure**, not Demand.

### Known limitations

- **OSM coverage/tagging is uneven** — counts are a proxy with real coverage risk; this
  should feed the Uncertainty penalty (coverage signal), not be read as ground truth.
- A single category (`shop=convenience`) is a narrow slice of commercial activity.
- Raw count favors larger wards; per-capita density partly corrects this but depends on
  the population layer being present.
- Near-boundary POIs may surface in two ward queries (de-duplicated by OSM id); wards
  missing from the response are omitted, not zero.

### Planned refinement

Add more categories (supermarket, cafe, restaurant) with per-category coverage flags,
and convert raw density into a calibrated competition-pressure signal with an explicit
coverage/confidence penalty.

## Accessibility Score — current implementation (v1, MLIT N02)

The third public-data metric. Status: **sample pipeline + tests complete; live deferred
(GIS)**.

- **Definition (current):** `accessibility_score` = min-max scaling (0..100) of the
  per-ward count of MLIT N02 railway stations (de-duplicated by station name so a
  station on several lines counts once). Optional `station_count_per_10k` gives a
  per-capita view when the e-Stat population layer is present (with a zero/missing-
  population guard so the value is NaN, never infinite).
- **Grain / source / transform:** Tokyo 23 wards; `src/tokyo_market_intel/sources/`
  `mlit.py` (N02 parsing) + `ingestion/mlit_accessibility.py` (pure transform). See
  `docs/data_sources.md` for the dataset, license, and the GIS constraint.
- **Provenance (`source_mode`):** `live_public` vs `sample_fixture` (default
  conservative). Every row carries 出典：国土数値情報（鉄道データ N02）（国土交通省）.

### What this score can and cannot say

- **Can say:** relative railway-station access across wards — a *station-access proxy*.
- **Cannot say:** demand, sales, or willingness to buy. Easy access to an area is not a
  market for it; this feeds the **Accessibility** signal, not Demand.

### Known limitations

- Station **count** is coarse: it ignores line importance, ridership, and transfer
  capacity (a 1-station ward on a major hub may out-serve a 3-station ward of minor
  lines). Ridership (e.g. MLIT S12) would refine this later.
- Min-max is relative to the wards present; absent wards are omitted, not zero.
- **Live is GIS-deferred:** N02 stations have no municipality code, so live ward
  assignment needs a point-in-polygon join (GeoPandas). Implemented offline via the
  sample fixture only, until the GIS dependency is opted into.

### Planned refinement

Add the spatial join (N03 boundaries) behind the optional `.[geo]` extra to produce the
live layer, then weight stations by ridership and distance-to-nearest-station.

## Cost Pressure Score — current implementation (v1, MLIT L01)

The fourth public-data metric. Status: **implemented (sample + live, GIS-free)**.

- **Definition (current):** `cost_pressure_score` = min-max scaling (0..100) of the
  per-ward **median** published land price (円/m²) from MLIT 地価公示 L01. The output
  also keeps `land_price_mean` and `observation_count`. Higher land price → higher cost
  pressure, which is a **negative** factor in the Opportunity score.
- **Grain / source / transform:** Tokyo 23 wards; `src/tokyo_market_intel/sources/`
  `mlit_cost.py` (L01 parsing) + `ingestion/mlit_cost.py` (pure transform). L01 carries
  the municipality code, so the per-ward aggregation is **GIS-free**.
- **Provenance (`source_mode`):** `live_public` vs `sample_fixture` (default
  conservative). Every row carries 出典：国土数値情報（地価公示データ L01）（国土交通省）.

### What this score can and cannot say

- **Can say:** relative land-price level across wards — a *cost-pressure proxy*.
- **Cannot say:** actual store rent, operating cost, or profit margin. Land price is an
  input cost signal, not a P&L figure.

### Known limitations

- Standard-site (地価公示) points are **sparse**, so a ward median is coarse and
  sensitive to which sites fall in the ward; `observation_count` exposes this.
- Median land price ignores land use, building height/FAR, and lease vs. own.
- Wards absent from the data are omitted, not zero.

### Planned refinement

Blend with 都道府県地価調査 (more points), segment by land use (commercial vs.
residential), and translate land price into a calibrated rent proxy with a coverage
penalty feeding the Uncertainty signal.

## Opportunity Score — public-data integration (v1)

Combines the four public-data layers on the Tokyo-23-ward code spine. Status:
**implemented** (`src/tokyo_market_intel/ingestion/opportunity.py`).

### Formula

```text
opportunity_score =
    w_demand        * demand_score
  + w_daytime       * daytime_activity_score   # Demand-axis refinement, w_daytime default 0
  + w_accessibility * accessibility_score
  - w_competition   * competition_pressure
  - w_cost          * cost_pressure
  - w_uncertainty   * data_uncertainty_penalty
```

- **Positive factors:** `demand_score` (e-Stat resident), `daytime_activity_score` (e-Stat
  昼間人口, **default weight 0**), `accessibility_score` (MLIT N02).
- **Negative factors (pressures):** `competition_pressure` (= OSM
  `commercial_density_score`), `cost_pressure` (= MLIT L01 `cost_pressure_score`).
- **Growth** is not yet implemented and is omitted (not faked).
- All inputs are 0..100. Missing layer scores are neutral-filled at 50; this is an
  **explicit assumption** and is reflected in the uncertainty penalty and confidence
  label (below) so a low-data ward is flagged, not silently flattered.
- Each layer's sign (positive vs. pressure) is **driven by the layer specification**
  (`_LAYER_SPECS`), not a hardcoded formula — adding a layer (e.g. Growth) only needs a
  spec row with its weight field and `is_positive` flag.
- Default weights: demand 1.0, accessibility 1.0, competition 0.7, cost 0.5,
  uncertainty 0.5. Weights are scenario parameters (dashboard sliders), not fixed truth.

### Data Uncertainty and Confidence

Per ward, from how many of the four layers are present and `live_public`:

- `available_layer_count` — layers with a row for the ward.
- `live_layer_count` — of those, how many are `live_public` (real public data).
- `missing_layer_count` = 4 − available.
- `data_uncertainty_penalty` = `100 * (missing + 0.5 * non_live_present) / 4`
  (0 = all four live; 50 = all four sample; 100 = all missing).
- `confidence_label`:
  - **Low** if any contributing layer is sample/unknown (not real), OR `live_layer_count ≤ 1`.
  - **Medium** if `live_layer_count == 2` and all contributors are live.
  - **High** if `live_layer_count ≥ 3` and all contributors are live.

A REAL ranking requires at least `MIN_LIVE_LAYERS_FOR_REAL` (=2) live layers; below that
the dashboard/script refuse to present a real opportunity ranking.

### What it can and cannot say

- **Can say:** a relative, scenario-weighted **screening** of where public signals are
  jointly favorable, with explicit confidence.
- **Cannot say:** revenue, actual demand, or profitability. **Public data supports
  screening, not a final investment decision.** Revenue-impact analysis would require
  internal company data (orders, CVR, delivery time, unit economics, competitor pricing).

### Limitations

- Each layer score is min-max relative to the wards present, so the integrated score is
  comparative, not absolute.
- Sample-fixture integration is a logic demo only and is never shown as real.
- Neutral-filling missing layers can flatter a ward with little data — the uncertainty
  penalty and confidence label are there to flag exactly that.

## Confidence logic

Each recommendation should carry a confidence label.

Suggested logic:

```text
High confidence:
  core metrics present, recent enough, ranking stable under weight changes

Medium confidence:
  most metrics present, some proxy risk, ranking moderately stable

Low confidence:
  missing data, stale data, high proxy risk, or unstable ranking
```

## Scenario presets (decision lenses)

A scenario preset is a named bundle of weights — a **decision lens**, not a change to the
data, its provenance, or the per-ward confidence. Presets live in
`src/tokyo_market_intel/scenarios.py` (one source of truth for the dashboard and these docs)
and are selected from the dashboard sidebar; **Custom** exposes the manual sliders.

| Preset | demand | daytime | accessibility | competition | cost | uncertainty | Lens |
|---|--:|--:|--:|--:|--:|--:|---|
| **Residential baseline** (default) | 1.0 | 0.0 | 1.0 | 0.7 | 0.5 | 0.5 | Resident population + cost; the decision-memo baseline. |
| **Daytime activity** | 0.7 | 1.0 | 1.0 | 0.7 | 0.5 | 0.5 | Weights daytime/commuter presence; central wards (Chiyoda/Minato/Chuo) rise. |
| **Cost-sensitive** | 1.0 | 0.0 | 1.0 | 0.7 | 1.0 | 0.5 | Strengthens the land-cost penalty; high-cost wards fall further. |
| **Custom** | — | — | — | — | — | — | Manual sliders. |

Residential baseline equals `DEFAULT_WEIGHTS`, so it reproduces the documented ranking.
Switching presets is **sensitivity analysis** — it never implies a revenue, demand, or
profitability forecast.

## Review standard

A Director-level reviewer should be able to inspect each metric and ask:

- What does this metric mean?
- What data source supports it?
- What is the proxy risk?
- Would the recommendation change if this weight changed?
- What internal data would make this materially better?
