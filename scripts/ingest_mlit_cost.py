"""Ingest the MLIT Tokyo-23-ward cost-pressure (land price) layer.

Thin CLI wrapper. Real logic lives in:

- ``tokyo_market_intel.sources.mlit_cost`` (L01 GeoJSON parsing)
- ``tokyo_market_intel.ingestion.mlit_cost`` (transform)

Modes
-----
- ``sample`` (default): no network. Loads the bundled L01-shaped fixture, runs the real
  transform, writes a separate ``*_sample.csv``.
- ``live``: parses a **locally downloaded** L01 GeoJSON for Tokyo (pass ``--geojson``).
  This is GIS-free — L01 carries the municipality code, so wards are aggregated by code
  with no spatial join. Download L01 from the MLIT site (link printed in live mode).

MLIT data is open data; outputs carry 出典：国土数値情報（地価公示データ L01）（国土交通省）.
Land price is a cost-pressure proxy only — not rent, operating cost, or profit margin.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from tokyo_market_intel.ingestion.mlit_cost import (  # noqa: E402
    SOURCE_MODE_LIVE,
    SOURCE_MODE_SAMPLE,
    build_cost_layer,
)
from tokyo_market_intel.sources.mlit_cost import (  # noqa: E402
    L01_DATALIST_URL,
    L01_DATASET,
    L01_LICENSE,
    parse_land_price_features,
)

DEFAULT_SAMPLE = REPO_ROOT / "data" / "sample" / "mlit_landprice_sample.json"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
DEFAULT_OUTPUT_LIVE = PROCESSED_DIR / "mlit_cost_tokyo23.csv"
DEFAULT_OUTPUT_SAMPLE = PROCESSED_DIR / "mlit_cost_tokyo23_sample.csv"


def resolve_mode(requested: str) -> str:
    """Resolve ``auto`` to ``sample`` (live needs a downloaded L01 file)."""

    return "sample" if requested == "auto" else requested


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["auto", "sample", "live"], default="auto")
    parser.add_argument("--sample-path", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--geojson",
        type=Path,
        default=None,
        help="Path to a locally downloaded L01 GeoJSON (required for --mode live).",
    )
    parser.add_argument("--code-key", default=None, help="Override L01 admin-code property key.")
    parser.add_argument("--price-key", default=None, help="Override L01 price property key.")
    args = parser.parse_args(argv)

    mode = resolve_mode(args.mode)

    parse_kwargs = {}
    if args.code_key:
        parse_kwargs["code_key"] = args.code_key
    if args.price_key:
        parse_kwargs["price_key"] = args.price_key

    if mode == "live":
        print(f"[live mode] Dataset: {L01_DATASET}")
        print(f"[live mode] Source/terms: {L01_DATALIST_URL} ({L01_LICENSE})")
        if not args.geojson:
            print(
                "[live mode] Missing --geojson. Download the L01 GeoJSON for Tokyo from "
                "the URL above and pass its path. (GIS-free: L01 has the admin code.)",
                file=sys.stderr,
            )
            return 2
        source_mode = SOURCE_MODE_LIVE
        out_path = args.out or DEFAULT_OUTPUT_LIVE
        geojson = json.loads(args.geojson.read_text(encoding="utf-8"))
    else:
        source_mode = SOURCE_MODE_SAMPLE
        out_path = args.out or DEFAULT_OUTPUT_SAMPLE
        print(f"[sample mode] No network. Reading fixture: {args.sample_path}")
        geojson = json.loads(args.sample_path.read_text(encoding="utf-8"))

    records = parse_land_price_features(geojson, **parse_kwargs)
    layer = build_cost_layer(records, source_mode=source_mode)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    layer.to_csv(out_path, index=False)

    print(f"Wrote {len(layer)} ward rows to {out_path} (source_mode={source_mode})")
    print(layer.to_string(index=False))
    print("\nAttribution: 出典：国土数値情報（地価公示データ L01）（国土交通省）")
    print("Note: land price is a cost-pressure proxy only — not rent or operating cost.")
    if mode == "sample":
        print(
            "Reminder: these figures come from the schema fixture and are NOT a real "
            f"finding (source_mode={SOURCE_MODE_SAMPLE}). Use --mode live --geojson <file>."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
