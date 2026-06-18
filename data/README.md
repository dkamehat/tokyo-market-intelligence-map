# Data directory policy

This project uses public and free data only.

## Directory convention

```text
data/
  raw/        # local downloads from official public data sources; not committed by default
  processed/  # generated analytical tables; not committed by default
```

## Rules

- Do not commit large raw files unless explicitly needed and license-compatible.
- Do not commit private, paid, scraped, or sensitive data.
- Every public source must be documented in `docs/data_sources.md` before it is used in the dashboard.
- If synthetic/demo data is used, label it clearly in the app and README.

## Why raw data is ignored

The portfolio should be reproducible through documented scripts and source links rather than by committing uncontrolled data dumps.
