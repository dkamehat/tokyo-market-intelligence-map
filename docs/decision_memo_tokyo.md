# Decision Memo — Tokyo Ward Opportunity Screening (v1)

**Status:** first-cut public-data screening · **Confidence: Medium** (2 of 4 coverage layers
live) · Data: e-Stat 2020 Census (resident + daytime population) + MLIT L01 2023 land price ·
Generated June 2026.

> This is a **first-cut, public-data opportunity screening** to narrow where to look next.
> It is **not** a revenue prediction, an actual-demand prediction, a profitability forecast,
> or a final site-selection / investment decision. Those require internal company data.

## Decision question

**Which Tokyo wards should a consumer business prioritize for expansion / local marketing /
micro-fulfillment — at the screening stage?**

## Recommendation

- **Priority screening candidates:** **Setagaya (世田谷), Nerima (練馬), Ota (大田).**
  Large resident base with land-cost pressure still in the lower half of the 23 wards — the
  most favorable demand-vs-cost balance in the current live data.
- **Treat with caution on cost grounds:** **Chiyoda (千代田)** (and the same central cluster,
  **Chuo / Minato**) — extreme land-cost pressure against a small *resident* population, so
  they rank at the bottom of this residential-demand screening. **This is not "avoid":** these
  are major daytime business districts whose opportunity a residential-population proxy cannot
  see (see Limitations). They are deprioritized *for this screening*, pending a daytime /
  workday-population layer.
- **Action:** use this only to **shortlist wards for deeper analysis**, not to commit sites.

## Opportunity Score readout (public-data integration)

From the live integrated layer (`opportunity_tokyo23.csv` / dashboard). REAL ranking
(≥ 2 `live_public` layers). All 23 wards are **Medium** confidence (`live_layer_count = 2`,
`missing_layer_count = 2`, `data_uncertainty_penalty = 50`).

**Top screening candidates**

| Rank | Ward | Opportunity score | Demand score (pop) | Cost pressure (median ¥/m²) | Confidence |
|---:|---|---:|---:|---:|---|
| 1 | Setagaya 世田谷 | 83.39 | 100.0 (948,147) | 13.2 (¥701,000) | Medium |
| 2 | Nerima 練馬 | 66.02 | 77.9 (753,045) | 3.7 (¥432,000) | Medium |
| 3 | Ota 大田 | 63.37 | 77.3 (748,291) | 7.9 (¥551,000) | Medium |

**Bottom of the residential-demand screening (cost-heavy central wards)**

| Rank | Ward | Opportunity score | Demand score (pop) | Cost pressure (median ¥/m²) | Confidence |
|---:|---|---:|---:|---:|---|
| 21 | Minato 港 | −31.42 | 22.0 (260,851) | 86.9 (¥2,780,000) | Medium |
| 22 | Chuo 中央 | −40.75 | 11.6 (169,318) | 84.8 (¥2,720,000) | Medium |
| 23 | Chiyoda 千代田 | −60.00 | 0.0 (66,758) | 100.0 (¥3,150,000) | Medium |

- The ranking is **REAL** (Demand + Cost are live), **not** a sample/demo.
- Every ward is **Medium** confidence — uniform, because only 2 of 4 layers are live for all
  wards. No ward reaches High (would need ≥ 3 live layers); none drops to Low (no sample data
  contaminates the live integration).

## Evidence summary

| Signal | Source (live) | What it indicates | Direction | Confidence |
|---|---|---|---:|---|
| Demand (resident) | e-Stat 2020 Population Census (resident population, ward grain) | residential customer-base scale (demographic proxy) | positive | live |
| Daytime activity | e-Stat 2020 Census 従業地・通学地集計 (昼間人口) | daytime / commuter presence proxy | positive (Demand-axis, **weight 0 default**) | live |
| Cost | MLIT L01 2023 地価公示 (median land price ¥/m²) | land-cost pressure proxy | negative (pressure) | live |
| Accessibility | MLIT N02 stations | ease of reaching/serving | — | **not live** (GIS-deferred) |
| Competition | OSM `shop=convenience` | commercial saturation | — | **not live** (not yet run) |
| Data quality | provenance + uncertainty penalty | reliability of the above | — | Medium (2/4 coverage layers live) |

Demand (resident) is a **demographic proxy** — not income, purchasing power, or actual
demand. Daytime activity (昼間人口) is a **daytime-presence proxy** — not demand, sales, or
revenue. Cost is a **land-cost-pressure proxy** — not store rent, operating cost, or profit
margin. The daytime layer is a **Demand-axis refinement**: it is not a 5th coverage layer,
so by default (daytime weight = 0) it leaves the baseline ranking and Medium confidence
unchanged, and the "daytime activity" scenario raises its weight to surface central wards.

## Why this recommendation

- **Setagaya, Nerima, Ota top the list because demand and cost pull the same way:** they
  carry the 1st/2nd/3rd largest resident populations (948k / 753k / 748k) while their median
  land price sits in the lower half of the 23 wards — a favorable demand-vs-cost balance.
- **Land cost is the decisive separator at the bottom:** Chiyoda, Chuo, and Minato have the
  highest median land prices (¥3.15M / ¥2.72M / ¥2.78M per m²) against small *resident*
  populations, so they score lowest *for residential demand screening*.
- **Confidence is capped at Medium by design:** only Demand and Cost are live (2/4 layers),
  so every ward carries a `data_uncertainty_penalty` of 50 and a Medium label. The system
  refuses to overstate certainty it does not have.

## Confidence

- **Medium** for all 23 wards.
- **Live layers: 2/4** — Demand (e-Stat), Cost (MLIT L01).
- **Missing layers: 2/4** — Accessibility (MLIT N02, live deferred — GIS) and Competition
  (OSM, live not yet run).
- A REAL ranking requires ≥ 2 live layers (met). High confidence would require ≥ 3 live and
  no sample contributors.

## Scenario sensitivity

Selectable as dashboard **scenario presets** (decision lenses, not data truth — provenance and
confidence are unchanged). Defined in `src/tokyo_market_intel/scenarios.py`.

| Scenario preset | Effect on this ranking | Notes |
|---|---|---|
| **Residential baseline** (default; daytime weight 0) | Setagaya / Nerima / Ota lead | Resident demand vs. cost; the baseline recommendation above (= `DEFAULT_WEIGHTS`). |
| **Daytime activity** (demand 0.7, daytime 1.0) | Central business wards rise sharply: **Chiyoda 23→17, Minato 21→11**; Setagaya still #1 | Real signal — daytime 昼間人口 (Minato 972,673; Chiyoda 903,780) vs. resident. Confidence stays Medium (daytime is a Demand-axis refinement, not added coverage). |
| **Cost-sensitive** (cost 1.0) | Pushes Chiyoda / Chuo / Minato further down; top is stable | Top wards have low cost, so they are robust to a higher cost weight. |
| **Custom** (manual sliders) | Any of the above, tuned by hand | Includes an access-led lens — but **Accessibility is not live yet**, so that lens is not yet answerable. |

The default (Residential baseline) top-3 shortlist is **stable** under the Cost-sensitive
preset. The **Daytime activity preset materially re-ranks** the central business wards upward
— exactly the resident-vs-daytime tension flagged below, now made explicit and tunable. An
access-led lens is still not answerable until Accessibility is live.

## Limitations (read before acting)

- **Residential ≠ commercial opportunity (now partly addressed).** The default Demand layer
  is *resident* population, which structurally favors residential wards (Setagaya) and
  penalizes daytime business districts (Chiyoda, Chuo, Minato). A live **daytime-activity
  layer** (昼間人口) is now integrated to expose this: e.g. Chiyoda's daytime population
  (903,780) is ~13.5× its resident population, Minato ~3.7×, whereas Setagaya is ~0.9×. It is
  a Demand-axis refinement at weight 0 by default (baseline unchanged); raising the daytime
  weight re-ranks the central wards up (Chiyoda 23→17, Minato 21→11). The remaining gap: pick
  the resident/daytime blend deliberately per use case (storefront vs. lunch/commuter trade).
- **The ranking currently rests on two axes (Demand + and Cost −).** Accessibility and
  Competition are **neutral-filled at 50** and reflected through the uncertainty penalty.
  That is a uniform offset, so it does not change the *order*, but it does inflate absolute
  scores — which is exactly what the penalty and the Medium label flag.
- **Land-price points are sparse.** Per-ward medians come from as few as ~24 standard sites
  (Sumida) up to ~143 (Setagaya); `observation_count` exposes this. Median land price ignores
  land use, FAR, and lease-vs-own.
- **Min-max scores are relative** to the 23-ward set, so the score is comparative, not
  absolute. Census data lags (5-year cycle).
- **Not** revenue, **not** actual demand, **not** profitability, **not** a final
  site-selection decision.

## What internal data would make this materially better

To move from screening to a real prioritization (and eventually revenue impact):

- orders / transactions, conversion rate, repeat rate / LTV
- delivery time / service-quality (SLA), customer acquisition cost, unit economics
- competitor pricing and promotion signals
- plus the two pending public layers (Accessibility live, Competition live) and a daytime-
  population demand refinement — which alone would lift confidence from Medium toward High.

## Final decision

> Based on current public-data signals, **shortlist Setagaya, Nerima, and Ota** for deeper
> analysis and **treat the central high-cost wards (Chiyoda, Chuo, Minato) cautiously at this
> stage** — but treat all of it as **first-cut market intelligence at Medium confidence**,
> to be revalidated once Accessibility and Competition are live, a daytime-population proxy is
> added, and internal demand / unit-economics data is available. Reproduction steps:
> `docs/live_data_runbook.md`.
