"""Build the integrated Opportunity Score layer from the four public-data layers.

Thin CLI. Loads the per-layer processed CSVs and integrates them with
``tokyo_market_intel.ingestion.opportunity``.

Modes
-----
- ``sample`` (default): reads the ``*_sample.csv`` layers and writes
  ``opportunity_tokyo23_sample.csv`` — a DEMO of the integration logic, NOT a real
  finding.
- ``live``: reads the live layer CSVs. A REAL opportunity ranking needs at least
  ``MIN_LIVE_LAYERS_FOR_REAL`` live_public layers; otherwise it refuses to write a
  misleading real file and tells you which layers are still needed.

Opportunity Score is first-cut public-data screening — not a revenue, demand, or
profitability estimate.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import pandas as pd  # noqa: E402

from tokyo_market_intel.ingestion.opportunity import (  # noqa: E402
    MIN_LIVE_LAYERS_FOR_REAL,
    SOURCE_MODE_LIVE,
    SOURCE_MODE_SAMPLE,
    count_live_layers,
    integrate_opportunity,
)

PROCESSED = REPO_ROOT / "data" / "processed"
LIVE_FILES = {
    "demand": PROCESSED / "estat_demand_tokyo23.csv",
    "accessibility": PROCESSED / "mlit_accessibility_tokyo23.csv",
    "competition": PROCESSED / "osm_competition_tokyo23.csv",
    "cost": PROCESSED / "mlit_cost_tokyo23.csv",
}
SAMPLE_FILES = {key: path.with_name(path.stem + "_sample.csv") for key, path in LIVE_FILES.items()}
# Daytime activity (Demand-axis refinement) is loaded separately and passed as
# daytime_layer. It does not count toward the 4-layer coverage/confidence.
DAYTIME_LIVE = PROCESSED / "estat_daytime_tokyo23.csv"
DAYTIME_SAMPLE = PROCESSED / "estat_daytime_tokyo23_sample.csv"
OUTPUT_LIVE = PROCESSED / "opportunity_tokyo23.csv"
OUTPUT_SAMPLE = PROCESSED / "opportunity_tokyo23_sample.csv"


def resolve_mode(requested: str) -> str:
    return "sample" if requested == "auto" else requested


def load_layers(files: dict[str, Path]) -> dict[str, pd.DataFrame | None]:
    layers: dict[str, pd.DataFrame | None] = {}
    for key, path in files.items():
        layers[key] = pd.read_csv(path, dtype={"area_code": str}) if path.exists() else None
    return layers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["auto", "sample", "live"], default="auto")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    mode = resolve_mode(args.mode)
    files = LIVE_FILES if mode == "live" else SAMPLE_FILES
    layers = load_layers(files)
    present = [key for key, df in layers.items() if df is not None]

    if mode == "live":
        live_count = count_live_layers(layers)
        if live_count < MIN_LIVE_LAYERS_FOR_REAL:
            missing = [k for k, df in layers.items() if df is None]
            print(
                f"[live mode] Not enough live public-data layers: {live_count} live, need "
                f">= {MIN_LIVE_LAYERS_FOR_REAL}. Generate more live layers (missing: "
                f"{', '.join(missing) or 'none'}). Refusing to write a REAL opportunity file.",
                file=sys.stderr,
            )
            return 3
        source_mode = SOURCE_MODE_LIVE
        out_path = args.out or OUTPUT_LIVE
    else:
        if not present:
            print(
                "[sample mode] No *_sample.csv layers found. Run the four sample ingests "
                "first (ingest_estat_population / ingest_osm_competition / "
                "ingest_mlit_accessibility / ingest_mlit_cost).",
                file=sys.stderr,
            )
            return 2
        source_mode = SOURCE_MODE_SAMPLE
        out_path = args.out or OUTPUT_SAMPLE

    daytime_path = DAYTIME_LIVE if mode == "live" else DAYTIME_SAMPLE
    daytime_layer = (
        pd.read_csv(daytime_path, dtype={"area_code": str}) if daytime_path.exists() else None
    )

    opportunity = integrate_opportunity(
        layers, source_mode=source_mode, daytime_layer=daytime_layer
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    opportunity.to_csv(out_path, index=False)

    print(f"Wrote {len(opportunity)} ward rows to {out_path} (source_mode={source_mode})")
    print(f"Layers used: {', '.join(present) or 'none'}")
    cols = ["area", "area_code", "opportunity_score", "confidence_label", "live_layer_count"]
    print(opportunity[cols].to_string(index=False))
    if mode == "sample":
        print(
            "\nReminder: this is a DEMO of the integration logic from sample fixtures — "
            f"NOT a real finding (source_mode={SOURCE_MODE_SAMPLE})."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
