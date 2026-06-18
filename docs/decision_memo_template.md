# Decision Memo Template

## Decision question

Where should a consumer business prioritize expansion, local marketing, or micro-fulfillment investment in Tokyo?

## Recommendation

Recommended priority areas:

1. Area A
2. Area B
3. Area C

Recommended action:

- [ ] expand / open
- [ ] test local marketing
- [ ] place micro-fulfillment node
- [ ] monitor only
- [ ] avoid for now

## Opportunity Score readout (public-data integration)

From the integrated layer (`opportunity_tokyo23.csv` / dashboard). This is **first-cut
public-data screening — not a revenue, demand, or profitability estimate.**

| Area | Opportunity score | Confidence | live_layer_count | data_uncertainty_penalty |
|---|---:|---|---:|---:|
| Area A | TBD | High / Medium / Low | n/4 | 0–100 |
| Area B | TBD | High / Medium / Low | n/4 | 0–100 |
| Area C | TBD | High / Medium / Low | n/4 | 0–100 |

- Is the ranking **REAL** (≥ 2 live_public layers) or a sample/demo? State which.
- Which wards have High confidence vs. Low (few live layers / sample data)?
- At **Medium** confidence (e.g. the current 2-live-layer state — Demand + Cost):
  *"This recommendation is based on two live public-data layers and should be treated as
  first-cut screening until Accessibility and Competition are live."*

## Evidence summary

| Signal | What it indicates | Direction | Confidence |
|---|---|---:|---|
| Demand | customer base / activity proxy | high / medium / low | high / medium / low |
| Accessibility | ease of reaching / serving the area | high / medium / low | high / medium / low |
| Competition | saturation pressure | high / medium / low | high / medium / low |
| Cost | investment or operating pressure | high / medium / low | high / medium / low |
| Data quality | reliability of the above | high / medium / low | high / medium / low |

## Why this recommendation

Write 3 to 5 bullets.

- Demand proxy is strong because ...
- Accessibility is strong because ...
- Competition pressure is acceptable because ...
- Confidence is limited by ...

## Scenario sensitivity

Explain whether the recommendation changes when weights change.

| Scenario | Top area | Interpretation |
|---|---|---|
| Growth-seeking | TBD | Demand/growth dominates |
| Cost-sensitive | TBD | Cost and competition penalties dominate |
| Operations-access | TBD | Station/road/accessibility dominates |

## Caveats

Public data limitations:

- No actual transaction data.
- No conversion rate.
- No delivery SLA / operational cost data.
- POI coverage can be uneven.
- Public demographic data may lag current behavior.

## What internal data would improve

Add internal data needed to move from first-cut intelligence to revenue impact estimation:

- orders / transactions
- conversion rate
- customer acquisition cost
- repeat rate / LTV
- delivery time / service quality
- campaign exposure
- competitor pricing and promotions

## Final decision

State the final recommendation in one sentence.

> Based on current public-data signals, prioritize [area] for [action], but treat the result as first-cut market intelligence until validated with internal demand and unit-economics data.
