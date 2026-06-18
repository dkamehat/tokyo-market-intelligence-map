"""e-Stat daytime-population source metadata — 国勢調査 従業地・通学地集計.

Access is shared with :mod:`tokyo_market_intel.sources.estat` (the generic
``getStatsData`` client + credential handling). This module only carries the
table-selection metadata and attribution for the **daytime population** layer, so the
ingestion transform and the CLI can reference one authoritative description.

Dataset: 国勢調査 令和2年国勢調査「従業地・通学地による人口・就業状態等集計」, table
「常住地又は従業地・通学地別人口（夜間人口・昼間人口）－全国，都道府県，市区町村」.
Daytime population (昼間人口) is a **daytime-activity proxy** — it counts people present in
a ward by place of work/schooling. It is NOT actual demand, sales, revenue, or profit.

License: 政府標準利用規約 第2.0版 (CC BY 4.0 compatible). Attribution required.

Like the L01 cost layer, the API ``statsDataId`` and the category codes that select the
daytime + sex-total cell are **version-specific** and are NOT hardcoded: pin the table via
``ESTAT_DAYTIME_STATS_DATA_ID`` (or ``--stats-data-id``) and confirm the daytime category
filter against the live table (see ``docs/data_sources.md``).
"""

from __future__ import annotations

DAYTIME_DATASET = (
    "国勢調査 令和2年 従業地・通学地集計：常住地又は従業地・通学地別人口（夜間人口・昼間人口）"
)
DAYTIME_DATALIST_URL = (
    "https://www.e-stat.go.jp/stat-search/files?page=1&layout=datalist&lid=000001296018"
)
DAYTIME_LICENSE = "政府標準利用規約 第2.0版 (CC BY 4.0 compatible)"
DAYTIME_ATTRIBUTION = "出典：令和2年国勢調査（総務省統計局）従業地・通学地集計"

# Env var for pinning the daytime table (kept separate from the resident-population
# ESTAT_STATS_DATA_ID so the two e-Stat layers do not collide).
DAYTIME_STATS_DATA_ID_ENV = "ESTAT_DAYTIME_STATS_DATA_ID"
