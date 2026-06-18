"""Ingest the e-Stat Tokyo-23-ward Demand layer.

Thin CLI wrapper. All real logic lives in:

- ``tokyo_market_intel.sources.estat`` (API access)
- ``tokyo_market_intel.ingestion.estat_population`` (transformation)

Modes
-----
- ``sample`` (default when ``ESTAT_APP_ID`` is unset): no network. Loads the bundled
  schema fixture, runs the real transform, and writes the processed table. Use this to
  develop and review the pipeline without credentials.
- ``live``: requires ``ESTAT_APP_ID`` and a ``statsDataId``. Calls the e-Stat API,
  saves the raw JSON to ``data/raw/``, and writes the processed table.

The application ID is read from the environment and is never printed.

Examples
--------
    python scripts/ingest_estat_population.py                # auto: sample if no appId
    python scripts/ingest_estat_population.py --mode sample
    ESTAT_APP_ID=... ESTAT_STATS_DATA_ID=... \\
        python scripts/ingest_estat_population.py --mode live --cat-filter @cat01=000
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Make the package importable without an editable install (CI uses src on path too).
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from tokyo_market_intel.ingestion.estat_population import (  # noqa: E402
    SOURCE_MODE_LIVE,
    SOURCE_MODE_SAMPLE,
    TOKYO_23_WARD_CODES,
    build_demand_layer,
)
from tokyo_market_intel.sources.estat import (  # noqa: E402
    EstatConfigError,
    fetch_stats_data,
    get_app_id,
    get_stats_data_id,
    redact,
)

DEFAULT_SAMPLE = REPO_ROOT / "data" / "sample" / "estat_population_sample.json"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
# Live real data and sample-fixture data are written to DIFFERENT default files so a
# sample run can never overwrite (or be mistaken for) the real public-data layer.
DEFAULT_OUTPUT_LIVE = PROCESSED_DIR / "estat_demand_tokyo23.csv"
DEFAULT_OUTPUT_SAMPLE = PROCESSED_DIR / "estat_demand_tokyo23_sample.csv"
DEFAULT_RAW = REPO_ROOT / "data" / "raw" / "estat_population_raw.json"


def parse_cat_filters(pairs: list[str]) -> dict[str, str]:
    """Parse ``--cat-filter @cat01=000`` arguments into a value-filter dict."""

    parsed: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"Invalid --cat-filter '{pair}'. Expected key=value.")
        key, value = pair.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def resolve_mode(requested: str) -> str:
    """Resolve ``auto`` to ``live`` when an appId is present, else ``sample``."""

    if requested != "auto":
        return requested
    return "live" if os.environ.get("ESTAT_APP_ID", "").strip() else "sample"


def load_sample(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["auto", "sample", "live"], default="auto")
    parser.add_argument("--sample-path", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output CSV. Defaults to the live file in live mode and a separate "
        "*_sample.csv in sample mode.",
    )
    parser.add_argument("--raw-out", type=Path, default=DEFAULT_RAW)
    parser.add_argument(
        "--cat-filter",
        action="append",
        default=[],
        help="Keep only VALUE rows matching key=value, e.g. @cat01=000 (sex total). "
        "Repeatable. Recommended for the census table to select the total category.",
    )
    parser.add_argument("--stats-data-id", default=None, help="Override ESTAT_STATS_DATA_ID.")
    args = parser.parse_args(argv)

    mode = resolve_mode(args.mode)
    value_filter = parse_cat_filters(args.cat_filter) or None

    if mode == "sample":
        source_mode = SOURCE_MODE_SAMPLE
        out_path = args.out or DEFAULT_OUTPUT_SAMPLE
        print(f"[sample mode] No live API call. Reading fixture: {args.sample_path}")
        payload = load_sample(args.sample_path)
    else:
        source_mode = SOURCE_MODE_LIVE
        out_path = args.out or DEFAULT_OUTPUT_LIVE
        try:
            get_app_id()  # validates ESTAT_APP_ID, raises a clear, secret-free error
            stats_data_id = args.stats_data_id or get_stats_data_id()
        except EstatConfigError as exc:
            print(f"[live mode] Configuration error: {exc}", file=sys.stderr)
            return 2
        print(f"[live mode] Calling e-Stat for statsDataId={stats_data_id} ...")
        try:
            payload = fetch_stats_data(
                stats_data_id,
                area_codes=list(TOKYO_23_WARD_CODES),
                extra=None,
            )
        except Exception as exc:
            # Redact before surfacing anything, in case a message echoes the request.
            print(f"[live mode] API call failed: {redact(str(exc))}", file=sys.stderr)
            return 1
        args.raw_out.parent.mkdir(parents=True, exist_ok=True)
        args.raw_out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        print(f"[live mode] Saved raw response to {args.raw_out}")

    demand = build_demand_layer(payload, value_filter=value_filter, source_mode=source_mode)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    demand.to_csv(out_path, index=False)

    print(f"Wrote {len(demand)} Tokyo-ward rows to {out_path} (source_mode={source_mode})")
    print(demand.to_string(index=False))
    if mode == "sample":
        print(
            "\nReminder: these figures come from the schema fixture and are NOT a real "
            "finding. They are written to a *_sample.csv and are labeled "
            f"source_mode={SOURCE_MODE_SAMPLE}. Run --mode live with ESTAT_APP_ID to "
            "produce the real public-data layer."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
