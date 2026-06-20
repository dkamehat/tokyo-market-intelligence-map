# Future Roadmap

Possible next directions for the Tokyo Market Intelligence Map. This is a statement of
**direction and possibility**, not a list of shipped features — anything not marked live
below is a candidate, not a commitment. The project stays a **first-cut public-data screening**
tool; none of the items below turn it into a revenue, actual-demand, or profitability forecast.

## Current baseline

- **Demand** — live verified (e-Stat resident population).
- **Cost** — live verified (MLIT L01 land price).
- **Daytime activity** — live verified as a **Demand-axis refinement** (e-Stat 昼間人口;
  default weight 0, so it does not change the baseline ranking or confidence).
- **Opportunity Score** — REAL ranking at **Medium** confidence (2 of 4 coverage layers live).
- **Scenario presets** — Residential baseline / Daytime activity / Cost-sensitive / Custom
  (decision lenses).
- **Decision memo, release checklist, screenshots** — available.
- **Competition** — sample pipeline ready; OSM live **pending**.
- **Accessibility** — sample pipeline ready; GIS live **deferred**.
- **Growth** — not implemented (omitted, not faked).

## Product direction

- This is a **first-cut public-data market-intelligence workflow**.
- The goal is **not** to predict revenue or make final site decisions.
- The goal **is** to support early-stage **area screening**, **scenario comparison**,
  **confidence labeling**, and **decision-memo creation** from reproducible public data.

## Development principles

- Public data first.
- Reproducibility over one-off analysis.
- Live/sample provenance must stay explicit.
- Confidence and uncertainty must be visible.
- Scenario presets are decision lenses, not data truth.
- Limitations must be documented before recommendations.

## Recommended next implementation order

### 1. OSM Competition live reliability

- **Why:** the Competition pipeline already exists; a successful live run would add a third
  coverage layer and could raise confidence beyond the current Medium.
- **Work:** retry off-peak; if needed, add Overpass endpoint selection / polite backoff; keep
  the ODbL `© OpenStreetMap contributors` attribution.
- **Risk:** public Overpass endpoint reliability (observed 429/504).
- **Success criteria:** 23 Tokyo wards; all `source_mode=live_public`; `competition_pressure`
  integrated; decision memo updated.

### 2. Accessibility live with GIS

- **Why:** accessibility is a core area-screening factor; it would move the model beyond a
  demand/cost-heavy screening.
- **Work:** add ward boundary polygons; point-in-polygon assignment for MLIT N02 station
  points; produce a station-density / accessibility score.
- **Risk:** a new GIS dependency (e.g. GeoPandas/Shapely) — propose before adding.
- **Success criteria:** station-to-ward assignment; `accessibility_score` `live_public`;
  improved confidence; docs explain the GIS assumptions.

### 3. Growth / trend layer

- **Why:** the current ranking is mostly a snapshot; growth signals help distinguish stable
  large markets from improving ones.
- **Candidate data:** population trend; daytime-population trend; land-price trend;
  household / age-composition trend.
- **Work:** a feasibility gate first; do not fake growth if the data is weak.
- **Success criteria:** `growth_score` added as a separate factor; a growth-oriented scenario
  preset.

### 4. Report / memo generation

- **Why:** the decision memo is currently written by hand; the next step is repeatable
  area-screening reports from the ranking table.
- **Work:** template-driven markdown report; top-N candidate summary; confidence / limitation
  blocks.
- **Success criteria:** one command generates a **draft** decision memo; human review still
  required.

### 5. Generalization beyond Tokyo 23 wards

- **Why:** the architecture could become a reusable public-data market-intelligence template.
- **Work:** region configuration; a reusable municipality spine; source-specific adapters.
- **Risk:** source availability differs by region.
- **Success criteria:** another city/region can be added without rewriting the app.

### 6. Deployment / hosted demo

- **Why:** lower friction for reviewers.
- **Caveat:** a public deployment should not require private API keys; sample/demo vs live
  must remain clearly separated.
- **Success criteria:** the hosted demo uses safe sample or pre-generated non-sensitive public
  outputs; the README stays clear about data provenance.

## Near-term next sprint recommendation

- **Recommended next sprint:** OSM Competition live reliability.
- **Rationale:** it is the shortest path to a third coverage layer; it directly addresses the
  current Medium-confidence limitation; and it does not require heavy GIS dependencies.
- **Fallback:** if the public Overpass endpoint stays unstable, switch to an Accessibility-GIS
  **design proposal** before any implementation.

## What remains intentionally out of scope

- Revenue forecast.
- Actual-demand prediction.
- Profitability forecast.
- Final site recommendation.
- Private company data.
- Paid data sources.
