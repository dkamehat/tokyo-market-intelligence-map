"""Ingest the MLIT Tokyo-23-ward accessibility (station) layer.

Thin CLI wrapper. Real logic lives in:

- ``tokyo_market_intel.sources.mlit`` (N02 parsing; ward assignment is deferred)
- ``tokyo_market_intel.ingestion.mlit_accessibility`` (transform)

Modes
-----
- ``sample`` (default): no network/GIS. Loads the bundled N02-shaped fixture (features
  already carry an ``area_code``), runs the real transform, writes a separate
  ``*_sample.csv``.
- ``live``: N02 stations carry no municipality code, so assigning them to wards needs a
  spatial join (GeoPandas). That is intentionally **not** implemented in this minimal
  step — live stops with a clear GIS opt-in proposal (exit code 3).

MLIT data is open data; outputs carry 出典：国土数値情報（鉄道データ N02）（国土交通省）.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import pandas as pd  # noqa: E402

from tokyo_market_intel.ingestion.mlit_accessibility import (  # noqa: E402
    SOURCE_MODE_SAMPLE,
    build_accessibility_layer,
)
from tokyo_market_intel.sources.mlit import (  # noqa: E402
    N02_DATALIST_URL,
    N02_DATASET,
    N02_LICENSE,
    MlitGisRequired,
    assign_stations_to_wards,
    parse_station_features,
)

DEFAULT_SAMPLE = REPO_ROOT / "data" / "sample" / "mlit_stations_sample.json"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
DEFAULT_OUTPUT_LIVE = PROCESSED_DIR / "mlit_accessibility_tokyo23.csv"
DEFAULT_OUTPUT_SAMPLE = PROCESSED_DIR / "mlit_accessibility_tokyo23_sample.csv"

DEMAND_LIVE = PROCESSED_DIR / "estat_demand_tokyo23.csv"
DEMAND_SAMPLE = PROCESSED_DIR / "estat_demand_tokyo23_sample.csv"


def resolve_mode(requested: str) -> str:
    """Resolve ``auto`` to ``sample`` (live needs a deferred GIS step)."""

    return "sample" if requested == "auto" else requested


def load_population(path: Path) -> dict[str, float] | None:
    if not path.exists():
        return None
    demand = pd.read_csv(path, dtype={"area_code": str})
    if "population" not in demand.columns:
        return None
    return dict(zip(demand["area_code"], demand["population"], strict=False))


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["auto", "sample", "live"], default="auto")
    parser.add_argument("--sample-path", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--population-csv", type=Path, default=None)
    args = parser.parse_args(argv)

    mode = resolve_mode(args.mode)

    if mode == "live":
        print(f"[live mode] Dataset: {N02_DATASET}")
        print(f"[live mode] Source/terms: {N02_DATALIST_URL} ({N02_LICENSE})")
        try:
            assign_stations_to_wards([])  # deferred: raises with a clear proposal
        except MlitGisRequired as exc:
            print(f"[live mode] GIS step deferred: {exc}", file=sys.stderr)
            return 3
        return 3

    source_mode = SOURCE_MODE_SAMPLE
    out_path = args.out or DEFAULT_OUTPUT_SAMPLE
    population_path = args.population_csv or DEMAND_SAMPLE
    print(f"[sample mode] No network/GIS. Reading fixture: {args.sample_path}")
    geojson = json.loads(args.sample_path.read_text(encoding="utf-8"))
    records = parse_station_features(geojson)

    population_by_code = load_population(population_path)
    if population_by_code is None:
        print(f"[info] No population file at {population_path}; skipping per-capita density.")

    layer = build_accessibility_layer(
        records,
        source_mode=source_mode,
        population_by_code=population_by_code,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    layer.to_csv(out_path, index=False)

    print(f"Wrote {len(layer)} ward rows to {out_path} (source_mode={source_mode})")
    print(layer.to_string(index=False))
    print("\nAttribution: 出典：国土数値情報（鉄道データ N02）（国土交通省）")
    print(
        "Reminder: these counts come from the schema fixture and are NOT a real "
        f"finding. Written to a *_sample.csv labeled source_mode={SOURCE_MODE_SAMPLE}. "
        "Live N02 ingestion needs a deferred GIS step (see --mode live)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
