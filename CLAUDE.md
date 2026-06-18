@AGENTS.md

## Claude Code specific workflow

Use Claude Code as the primary builder for this project.

Recommended process:

1. Read `README.md`, `docs/metric_design.md`, and `docs/implementation_plan.md`.
2. Create or update a short plan before changing files.
3. Keep changes small enough to review.
4. Run tests or state clearly why tests cannot run.
5. Commit in coherent units.

## Default task order

1. Make the Streamlit MVP run with synthetic data.
2. Add scoring tests.
3. Add data source inventory.
4. Add one real public-data ingestion path.
5. Add data-quality and confidence scoring.
6. Write the decision memo.
7. Prepare a portfolio-ready README and screenshot.

## Claude review checklist

When reviewing your own work, be skeptical:

- Does the first screen answer `so what?`
- Are formulas inspectable?
- Is synthetic data clearly labeled?
- Would a Director-level BI reviewer trust the caveats?
- Is the project clearly BI / Intelligence, not only BizOps?
