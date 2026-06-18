"""Ingest the e-Stat Tokyo-23-ward daytime-activity layer (昼間人口).

Thin CLI wrapper. Real logic lives in:

- ``tokyo_market_intel.sources.estat`` (generic getStatsData client + credentials)
- ``tokyo_market_intel.sources.estat_daytime`` (table metadata + attribution)
- ``tokyo_market_intel.ingestion.estat_daytime`` (transform)

Modes
-----
- ``sample`` (default when no appId): no network. Loads the bundled schema fixture and
  writes a SEPARATE ``*_sample.csv`` (``source_mode=sample_fixture``), never shown as real.
- ``live``: requires ``ESTAT_APP_ID`` and the daytime table's ``statsDataId``
  (``ESTAT_DAYTIME_STATS_DATA_ID`` or ``--stats-data-id``). Live mode **defaults** to the
  verified daytime cell ``@cat01=180`` (昼間人口 total), so ``--cat-filter`` is optional;
  override it if a different table version renumbers the category.

Daytime population is a **daytime-activity proxy** — NOT actual demand, sales, revenue, or
profit. The application ID and statsDataId are read from the environment and never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import pandas as pd  # noqa: E402

from tokyo_market_intel.ingestion.estat_daytime import (  # noqa: E402
    SOURCE_MODE_LIVE,
    SOURCE_MODE_SAMPLE,
    build_daytime_layer,
)
from tokyo_market_intel.ingestion.estat_population import TOKYO_23_WARD_CODES  # noqa: E402
from tokyo_market_intel.sources.estat import (  # noqa: E402
    EstatConfigError,
    fetch_stats_data,
    get_app_id,
    redact,
)
from tokyo_market_intel.sources.estat_daytime import (  # noqa: E402
    DAYTIME_DATALIST_URL,
    DAYTIME_DATASET,
    DAYTIME_LICENSE,
    DAYTIME_STATS_DATA_ID_ENV,
)

DEFAULT_SAMPLE = REPO_ROOT / "data" / "sample" / "estat_daytime_sample.json"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
DEFAULT_OUTPUT_LIVE = PROCESSED_DIR / "estat_daytime_tokyo23.csv"
DEFAULT_OUTPUT_SAMPLE = PROCESSED_DIR / "estat_daytime_tokyo23_sample.csv"
DEFAULT_RAW = REPO_ROOT / "data" / "raw" / "estat_daytime_raw.json"

# Default category filters are mode-specific so a live run cannot silently use the sample
# fixture's codes. The SAMPLE fixture uses illustrative codes; the LIVE table's verified
# daytime (昼間人口 total) cell is cat01=180. Override either with --cat-filter.
DEFAULT_SAMPLE_FILTER = {"@cat01": "01", "@cat02": "000"}
DEFAULT_LIVE_FILTER = {"@cat01": "180"}

# Resident-population files, read (if present) only to attach a display-only
# daytime/resident ratio. Never required.
RESIDENT_LIVE = PROCESSED_DIR / "estat_demand_tokyo23.csv"
RESIDENT_SAMPLE = PROCESSED_DIR / "estat_demand_tokyo23_sample.csv"


def parse_cat_filters(pairs: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"Invalid --cat-filter '{pair}'. Expected key=value.")
        key, value = pair.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def resolve_mode(requested: str) -> str:
    if requested != "auto":
        return requested
    return "live" if os.environ.get("ESTAT_APP_ID", "").strip() else "sample"


def default_filter_for_mode(mode: str) -> dict[str, str]:
    """Mode-specific default category filter (live never falls back to the fixture codes)."""

    return DEFAULT_LIVE_FILTER if mode == "live" else DEFAULT_SAMPLE_FILTER


def load_resident_population(path: Path) -> dict[str, float] | None:
    """Return a ward-code -> resident population map from a demand CSV, if available."""

    if not path.exists():
        return None
    frame = pd.read_csv(path, dtype={"area_code": str})
    if "population" not in frame.columns or "area_code" not in frame.columns:
        return None
    return {
        str(code): float(pop)
        for code, pop in zip(frame["area_code"], frame["population"], strict=False)
        if pd.notna(pop)
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["auto", "sample", "live"], default="auto")
    parser.add_argument("--sample-path", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--raw-out", type=Path, default=DEFAULT_RAW)
    parser.add_argument(
        "--cat-filter",
        action="append",
        default=[],
        help="Override the daytime cell filter, e.g. @cat01=180. Repeatable. Defaults are "
        "mode-specific (live: @cat01=180; sample: the fixture codes). Live codes are "
        "table-version specific — override if the table renumbers the category.",
    )
    parser.add_argument(
        "--stats-data-id",
        default=None,
        help=f"Override {DAYTIME_STATS_DATA_ID_ENV} (the daytime table's statsDataId).",
    )
    args = parser.parse_args(argv)

    mode = resolve_mode(args.mode)
    # Mode-specific default so live never silently falls back to the sample fixture's codes.
    value_filter = parse_cat_filters(args.cat_filter) or default_filter_for_mode(mode)

    if mode == "sample":
        source_mode = SOURCE_MODE_SAMPLE
        out_path = args.out or DEFAULT_OUTPUT_SAMPLE
        resident = load_resident_population(RESIDENT_SAMPLE)
        print(f"[sample mode] No live API call. Reading fixture: {args.sample_path}")
        payload = json.loads(args.sample_path.read_text(encoding="utf-8"))
    else:
        source_mode = SOURCE_MODE_LIVE
        out_path = args.out or DEFAULT_OUTPUT_LIVE
        resident = load_resident_population(RESIDENT_LIVE)
        try:
            get_app_id()  # validates ESTAT_APP_ID (clear, secret-free error)
            stats_data_id = args.stats_data_id or os.environ.get(
                DAYTIME_STATS_DATA_ID_ENV, ""
            ).strip()
        except EstatConfigError as exc:
            print(f"[live mode] Configuration error: {exc}", file=sys.stderr)
            return 2
        if not stats_data_id:
            print(
                f"[live mode] Missing the daytime table id. Pin the table "
                f"({DAYTIME_DATASET}) and export {DAYTIME_STATS_DATA_ID_ENV} (or pass "
                f"--stats-data-id). Catalog: {DAYTIME_DATALIST_URL} ({DAYTIME_LICENSE}).",
                file=sys.stderr,
            )
            return 2
        print("[live mode] Calling e-Stat for the daytime table ...")
        try:
            payload = fetch_stats_data(stats_data_id, area_codes=list(TOKYO_23_WARD_CODES))
        except Exception as exc:
            print(f"[live mode] API call failed: {redact(str(exc))}", file=sys.stderr)
            return 1
        args.raw_out.parent.mkdir(parents=True, exist_ok=True)
        args.raw_out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        print(f"[live mode] Saved raw response to {args.raw_out}")

    layer = build_daytime_layer(
        payload,
        value_filter=value_filter,
        source_mode=source_mode,
        resident_population_by_code=resident,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    layer.to_csv(out_path, index=False)

    print(f"Wrote {len(layer)} Tokyo-ward rows to {out_path} (source_mode={source_mode})")
    print(layer.to_string(index=False))
    print("\nAttribution: 出典：令和2年国勢調査（総務省統計局）従業地・通学地集計")
    print("Note: daytime population is a daytime-activity proxy — not demand, sales, or revenue.")
    if mode == "sample":
        print(
            "\nReminder: these figures come from the schema fixture and are NOT a real "
            f"finding (source_mode={SOURCE_MODE_SAMPLE}). Run --mode live with ESTAT_APP_ID "
            f"and {DAYTIME_STATS_DATA_ID_ENV} to produce the real layer."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
