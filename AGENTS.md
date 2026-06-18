# AGENTS.md

## Project purpose

Build a portfolio-grade BI / Market Intelligence project, not a generic dashboard or notebook.

The product answers:

> Where should a consumer business prioritize expansion, local marketing, or micro-fulfillment investment in Tokyo?

The core evaluation standard is whether a senior BI / Intelligence reviewer sees a clear decision system with inspectable metrics, data lineage, and explicit uncertainty.

## Working principles

- Keep the user-facing story simple.
- Keep the metric and data design defensible.
- Do not overclaim from public data.
- Treat public data as first-cut intelligence, not revenue truth.
- Prioritize explainability over ML complexity.
- Write assumptions and caveats next to the output, not hidden in a footnote.

## Role positioning

This project should support BI / Intelligence roles:

- BI Analyst: stakeholder decision, KPI design, dashboard, insight narrative.
- BI Engineer: reproducible pipeline, data model, tests, deployment readiness.
- Analytics Engineer: metric layer, transformation logic, semantic definitions.
- Market Intelligence: public data synthesis, opportunity / competition assessment.

Avoid making the project look like a generic BizOps strategy case. The emphasis is the intelligence product and decision infrastructure.

## Technical stack

Default:

- Python 3.11+
- pandas / numpy
- DuckDB
- Streamlit
- pytest
- ruff

Optional geospatial layer:

- GeoPandas
- shapely
- h3

## Repository expectations

- Keep formulas in `src/tokyo_market_intel/scoring.py`, not duplicated in the app.
- Keep source inventory in `docs/data_sources.md`.
- Keep metric definitions in `docs/metric_design.md`.
- Keep dashboard code in `app/streamlit_app.py`.
- Use synthetic/demo data only until public-data ingestion is implemented.
- Clearly label synthetic data as synthetic in UI and docs.

## Testing expectations

Before opening a PR or considering a task complete:

```bash
cd tokyo-market-intelligence-map
pytest
ruff check .
```

If tests are not implemented yet, add them before expanding features.

## Portfolio quality bar

A reviewer should be able to answer these in under 3 minutes:

1. What business decision does this support?
2. Which metrics drive the recommendation?
3. Which data sources feed each metric?
4. What are the known limitations?
5. How would this improve with internal company data?

## Do not do

- Do not add private, scraped, paid, or unverifiable data.
- Do not claim true demand, sales, or revenue prediction from public data alone.
- Do not use ML unless it clearly improves the decision system.
- Do not hide low-confidence outputs.
- Do not build many charts without a decision narrative.
