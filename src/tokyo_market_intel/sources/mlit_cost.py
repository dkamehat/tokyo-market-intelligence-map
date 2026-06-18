"""MLIT 地価公示 (Land Price Public Notice) source helpers — dataset L01.

Access / parsing only — no analytical transformation (that lives in
`tokyo_market_intel.ingestion.mlit_cost`).

Dataset: 国土数値情報 **地価公示データ L01**. Each standard-site point carries an
**administrative-area code** and the published land price (円/m²), among other fields.
Because the municipality code is present, aggregating to a ward is **GIS-free** (group
by code) — no spatial join needed, unlike the N02 station layer.

Land price is a **cost-pressure proxy only** — NOT actual store rent, operating cost,
or profit margin.

License: L01 from 2020 onward is open data under MLIT's applicable terms (CC BY
compatible); confirm per dataset/version. Attribution required.

Note: L01 attribute numbering varies by version, so the property keys for the admin
code and price are configurable (defaults below match recent versions). Confirm the
keys for the version you download.
"""

from __future__ import annotations

L01_DATASET = "国土数値情報 地価公示データ L01 (standard-site land prices)"
L01_DATALIST_URL = "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-L01-v3_1.html"
L01_FORMATS = "GML (JPGIS2014), Shapefile, GeoJSON"
L01_LICENSE = "open data (2020+ applicable terms; CC BY compatible) — confirm per version"
L01_ATTRIBUTION = "出典：国土数値情報（地価公示データ L01）（国土交通省）"

# Default L01 GeoJSON property keys (version-dependent — override if needed).
DEFAULT_CODE_KEY = "L01_017"   # 行政区域コード (administrative-area code)
DEFAULT_PRICE_KEY = "L01_019"  # 価格 (land price, 円/m²)


class MlitCostError(RuntimeError):
    """Raised when L01 land-price access/parsing fails."""


def parse_land_price_features(
    geojson: dict,
    *,
    code_key: str = DEFAULT_CODE_KEY,
    price_key: str = DEFAULT_PRICE_KEY,
) -> list[dict]:
    """Parse an L01 land-price GeoJSON FeatureCollection into records.

    GIS-free. Returns one record per feature with ``area_code`` (the municipality code
    from ``code_key``) and ``price`` (raw value from ``price_key``; coerced later). No
    geometry/spatial work is needed because the admin code is in the attributes.
    """

    records: list[dict] = []
    for feature in geojson.get("features", []):
        props = feature.get("properties", {}) or {}
        records.append(
            {
                "area_code": props.get(code_key),
                "price": props.get(price_key),
            }
        )
    return records
