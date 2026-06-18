"""MLIT National Land Numerical Information (国土数値情報) source helpers.

Access / parsing only — no analytical transformation (that lives in
`tokyo_market_intel.ingestion.mlit_accessibility`).

Dataset: **Railway data N02** (鉄道データ), Station layer (駅). Point geometry with
attributes: line name (N02_003), operator (N02_004), station name (N02_005), station
code, group code. **It carries no administrative-area code**, so assigning a station to
a ward needs a spatial join (point-in-polygon vs. N03 ward boundaries) = GIS.

Per the project's minimal-first rule, the GIS spatial join is **not implemented here**.
``parse_station_features`` is GIS-free and works on a Station GeoJSON whose features
already carry an injected ``area_code`` (the sample fixture, or a future GIS step).
``assign_stations_to_wards`` deliberately raises :class:`MlitGisRequired` to propose the
GeoPandas opt-in rather than silently adding a heavy dependency.

License: N02 from 2020 onward is open data under MLIT's applicable terms (CC BY
compatible); confirm per dataset/version before use. Attribution is required.
"""

from __future__ import annotations

# Dataset identity (recorded so docs/UI are self-describing).
N02_DATASET = "国土数値情報 鉄道データ N02 (Station layer / 駅)"
N02_VERSION = "2022 (令和4年, base date 2022-12-31)"
N02_DATALIST_URL = "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N02-2022.html"
N02_FORMATS = "GML (JPGIS2014), Shapefile, GeoJSON"
N02_LICENSE = "open data (2020+ applicable terms; CC BY compatible) — confirm per version"
MLIT_ATTRIBUTION = "出典：国土数値情報（鉄道データ N02）（国土交通省）"

# N02 GeoJSON property keys for the Station layer.
PROP_LINE = "N02_003"
PROP_OPERATOR = "N02_004"
PROP_STATION = "N02_005"


class MlitError(RuntimeError):
    """Base error for MLIT source access."""


class MlitGisRequired(MlitError):
    """Raised when ward assignment needs a spatial join that is intentionally deferred."""


def _point_coords(geometry: dict | None) -> tuple[float | None, float | None]:
    """Return (lon, lat) for a Point geometry, else (None, None)."""

    if not geometry or geometry.get("type") != "Point":
        return None, None
    coords = geometry.get("coordinates") or []
    if len(coords) < 2:
        return None, None
    return coords[0], coords[1]


def parse_station_features(geojson: dict) -> list[dict]:
    """Parse an N02 Station GeoJSON FeatureCollection into station records.

    GIS-free. Returns one record per feature with: ``station_name``, ``line``,
    ``operator``, ``lon``, ``lat``, and ``area_code`` (read from properties when
    present — injected by the sample fixture or a future GIS assignment step).
    """

    records: list[dict] = []
    for feature in geojson.get("features", []):
        props = feature.get("properties", {}) or {}
        lon, lat = _point_coords(feature.get("geometry"))
        records.append(
            {
                "area_code": props.get("area_code"),
                "station_name": props.get(PROP_STATION),
                "line": props.get(PROP_LINE),
                "operator": props.get(PROP_OPERATOR),
                "lon": lon,
                "lat": lat,
            }
        )
    return records


def assign_stations_to_wards(records: list[dict]) -> list[dict]:
    """Assign each station to a Tokyo ward — DEFERRED (needs a spatial join).

    N02 stations carry no municipality code, so this requires a point-in-polygon join
    against N03 ward boundaries (GeoPandas/shapely). That dependency is intentionally
    not added in this minimal step. Opt into it deliberately in a follow-up
    (``pip install -e ".[geo]"``) and implement the join there.
    """

    raise MlitGisRequired(
        "Assigning N02 stations to wards needs a spatial join (point-in-polygon vs. N03 "
        "ward boundaries), which requires GeoPandas/shapely. This minimal step does not "
        "add that dependency. Use sample mode to exercise the pipeline, or opt into "
        '`pip install -e ".[geo]"` and implement the join in a follow-up step.'
    )
