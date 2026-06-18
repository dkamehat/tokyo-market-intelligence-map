"""Overpass API client (access only).

Responsible for *access only*: building an Overpass QL query and returning the parsed
elements. No analytical transformation here — that lives in
`tokyo_market_intel.ingestion.osm_competition`.

OpenStreetMap data is licensed under the ODbL (attribution + share-alike). Any output
derived from it must display: "© OpenStreetMap contributors".

Politeness / fair use (public Overpass instances):
- Send queries serially (never in parallel) from one host.
- Keep a small delay between queries; cache results locally.
- A 429 means rate-limited — back off, do not hammer.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSM_ATTRIBUTION = "© OpenStreetMap contributors"
DEFAULT_TIMEOUT = 60.0

# Japanese ward names for Overpass area matching (special wards are admin_level 7).
TOKYO_23_WARDS_JA: dict[str, str] = {
    "13101": "千代田区",
    "13102": "中央区",
    "13103": "港区",
    "13104": "新宿区",
    "13105": "文京区",
    "13106": "台東区",
    "13107": "墨田区",
    "13108": "江東区",
    "13109": "品川区",
    "13110": "目黒区",
    "13111": "大田区",
    "13112": "世田谷区",
    "13113": "渋谷区",
    "13114": "中野区",
    "13115": "杉並区",
    "13116": "豊島区",
    "13117": "北区",
    "13118": "荒川区",
    "13119": "板橋区",
    "13120": "練馬区",
    "13121": "足立区",
    "13122": "葛飾区",
    "13123": "江戸川区",
}


class OverpassError(RuntimeError):
    """Raised when an Overpass API call fails or is rate-limited."""


def build_convenience_query(ward_name_ja: str, *, timeout: int = 25) -> str:
    """Build an Overpass QL query for ``shop=convenience`` nodes in one ward.

    The spatial join is offloaded to the Overpass ``area`` filter (server-side), so no
    local GIS is needed for a first-cut ward-grain count.
    """

    return (
        f"[out:json][timeout:{timeout}];"
        f'area["name"="{ward_name_ja}"]["admin_level"="7"]->.w;'
        f'node(area.w)["shop"="convenience"];'
        f"out body;"
    )


def fetch_elements(query: str, *, timeout: float = DEFAULT_TIMEOUT) -> list[dict]:
    """Run a single Overpass query and return its ``elements`` list.

    Network / decode failures are wrapped in :class:`OverpassError`. A 429 is surfaced
    explicitly so callers can back off.
    """

    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    request = urllib.request.Request(
        OVERPASS_URL,
        data=data,
        headers={"Accept": "application/json", "User-Agent": "tokyo-market-intel/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise OverpassError(
                "Overpass rate-limited this request (HTTP 429). Slow down and retry."
            ) from None
        raise OverpassError(f"Overpass returned HTTP {exc.code}.") from None
    except urllib.error.URLError as exc:
        raise OverpassError(f"Could not reach Overpass ({exc.reason}).") from None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OverpassError(f"Overpass returned non-JSON content: {exc}.") from None

    return payload.get("elements", [])


def fetch_convenience_pois_by_ward(
    ward_codes: list[str] | None = None,
    *,
    sleep: float = 1.0,
    timeout: float = DEFAULT_TIMEOUT,
    max_wards: int | None = None,
) -> list[dict]:
    """Fetch ``shop=convenience`` POIs for each ward (live), tagging each with its code.

    One small query per ward, run **serially** with a delay between them to respect
    Overpass fair use. Each returned element gets an injected ``area_code`` so the pure
    transform can group by ward without any GIS. ``max_wards`` caps the run for a small
    smoke test.
    """

    codes = ward_codes or list(TOKYO_23_WARDS_JA.keys())
    if max_wards is not None:
        codes = codes[:max_wards]

    collected: list[dict] = []
    last_index = len(codes) - 1
    for index, code in enumerate(codes):
        ward_ja = TOKYO_23_WARDS_JA[code]
        elements = fetch_elements(build_convenience_query(ward_ja), timeout=timeout)
        for element in elements:
            element["area_code"] = code
        collected.extend(elements)
        if sleep and index < last_index:
            time.sleep(sleep)
    return collected
