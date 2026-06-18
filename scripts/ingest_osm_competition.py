"""Ingest the OSM/Overpass Tokyo-23-ward competition-density layer.

Thin CLI wrapper. Real logic lives in:

- ``tokyo_market_intel.sources.overpass`` (Overpass access)
- ``tokyo_market_intel.ingestion.osm_competition`` (transform)

Modes
-----
- ``sample`` (default): no network. Loads the bundled Overpass-shaped fixture, runs the
  real transform, and writes a separate ``*_sample.csv``. Use this to develop/review.
- ``live``: calls Overpass once per ward (serially, with a delay), scoped to
  ``shop=convenience``. Must be requested explicitly. Be gentle: use ``--max-wards`` for
  a small smoke test and keep ``--sleep`` > 0.

OSM data is ODbL — outputs carry "© OpenStreetMap contributors".

Examples
--------
    python scripts/ingest_osm_competition.py                  # sample mode (no network)
    python scripts/ingest_osm_competition.py --mode live --max-wards 1   # small smoke
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import pandas as pd  # noqa: E402

from tokyo_market_intel.ingestion.osm_competition import (  # noqa: E402
    SOURCE_MODE_LIVE,
    SOURCE_MODE_SAMPLE,
    build_competition_layer,
)
from tokyo_market_intel.sources.overpass import (  # noqa: E402
    OverpassError,
    fetch_convenience_pois_by_ward,
)

DEFAULT_SAMPLE = REPO_ROOT / "data" / "sample" / "osm_convenience_sample.json"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
DEFAULT_OUTPUT_LIVE = PROCESSED_DIR / "osm_competition_tokyo23.csv"
DEFAULT_OUTPUT_SAMPLE = PROCESSED_DIR / "osm_competition_tokyo23_sample.csv"

# Optional population sources (to compute per-capita density), matching demand outputs.
DEMAND_LIVE = PROCESSED_DIR / "estat_demand_tokyo23.csv"
DEMAND_SAMPLE = PROCESSED_DIR / "estat_demand_tokyo23_sample.csv"


def resolve_mode(requested: str) -> str:
    """Resolve ``auto`` to ``sample`` (Overpass needs no credential to gate on).

    Live network calls must be requested explicitly with ``--mode live``.
    """

    return "sample" if requested == "auto" else requested


def load_population(path: Path) -> dict[str, float] | None:
    """Load ``{area_code: population}`` from a demand CSV, if present."""

    if not path.exists():
        return None
    demand = pd.read_csv(path, dtype={"area_code": str})
    if "population" not in demand.columns:
        return None
    return dict(zip(demand["area_code"], demand["population"], strict=False))


def main(argv: list[str] | None = None) -> int:
    # Output carries the "©" attribution; keep stdout UTF-8 so it never crashes on a
    # legacy console encoding (e.g. Windows cp932). The CSV is written UTF-8 regardless.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["auto", "sample", "live"], default="auto")
    parser.add_argument("--sample-path", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--population-csv", type=Path, default=None)
    parser.add_argument("--max-wards", type=int, default=None, help="Cap live ward queries.")
    parser.add_argument("--sleep", type=float, default=1.0, help="Delay between live queries.")
    args = parser.parse_args(argv)

    mode = resolve_mode(args.mode)

    if mode == "sample":
        source_mode = SOURCE_MODE_SAMPLE
        out_path = args.out or DEFAULT_OUTPUT_SAMPLE
        population_path = args.population_csv or DEMAND_SAMPLE
        print(f"[sample mode] No network. Reading fixture: {args.sample_path}")
        payload = json.loads(args.sample_path.read_text(encoding="utf-8"))
        elements = payload.get("elements", [])
    else:
        source_mode = SOURCE_MODE_LIVE
        out_path = args.out or DEFAULT_OUTPUT_LIVE
        population_path = args.population_csv or DEMAND_LIVE
        print("[live mode] Querying Overpass per ward (serial, throttled) ...")
        try:
            elements = fetch_convenience_pois_by_ward(
                sleep=args.sleep,
                max_wards=args.max_wards,
            )
        except OverpassError as exc:
            print(f"[live mode] Overpass call failed: {exc}", file=sys.stderr)
            return 1

    population_by_code = load_population(population_path)
    if population_by_code is None:
        print(f"[info] No population file at {population_path}; skipping per-capita density.")

    layer = build_competition_layer(
        elements,
        source_mode=source_mode,
        population_by_code=population_by_code,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    layer.to_csv(out_path, index=False)

    print(f"Wrote {len(layer)} ward rows to {out_path} (source_mode={source_mode})")
    print(layer.to_string(index=False))
    print("\nAttribution: © OpenStreetMap contributors (ODbL).")
    if mode == "sample":
        print(
            "Reminder: these counts come from the schema fixture and are NOT a real "
            f"finding. Written to a *_sample.csv labeled source_mode={SOURCE_MODE_SAMPLE}. "
            "Run --mode live to query real OSM data."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
