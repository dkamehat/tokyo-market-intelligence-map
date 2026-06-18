# Public Data Sources

This project must use only public and free data. Official sources are preferred over
mirrors. Every source below is documented with enough metadata that a senior BI /
Intelligence reviewer can audit credibility, license compliance, and data lineage
before any metric is built on top of it.

Facts in this document (URLs, license terms, API-key requirements) were verified
against primary sources in June 2026. Sources are linked at the bottom.

## Source inventory (summary)

| Source | Provider | Access | Geospatial | License | MVP / v1 / later |
|---|---|---|---|---|---|
| e-Stat | Japanese government statistics portal (National Statistics Center; multi-ministry) | REST API (free appId) | low (join by municipality code) | Gov Standard Terms 2.0 ≈ CC BY 4.0 | **v1** |
| MLIT National Land Numerical Information | MLIT | bulk file download (no API) | high (vector GIS) | mostly CC BY 4.0, some non-commercial — per dataset | v1 / later |
| Tokyo Open Data Catalog | Tokyo Metropolitan Government | CKAN portal + data API | varies by dataset | CC BY 4.0 (default) | v1 / later |
| OpenStreetMap / Overpass | OSM community / Overpass API | Overpass QL API (no key, rate-limited) | medium (lat/lon points → spatial join) | ODbL (attribution + share-alike) | v1 |
| RESAS | Cabinet Office regional economy data | API (key) | low–medium | terms require verification | later |
| GDELT | GDELT Project | API / BigQuery | n/a (event/document) | open, attribution | later (phase 2 intelligence) |

---

## 1. e-Stat (政府統計の総合窓口)

- **official URL**: https://www.e-stat.go.jp/api/
- **provider**: Japanese government statistics portal operated by the National
  Statistics Center (統計センター) for the Statistics Bureau, providing statistics
  aggregated from multiple ministries and agencies (not a single ministry).
- **intended use**: demand layer — strictly a demographic / household-structure proxy
  for demand. Population, household count, and age structure (incl. daytime vs.
  nighttime population where available). This is **not** a measure of income,
  purchasing power, or actual demand; public data only supports demographic structure
  as a demand proxy.
- **geographic grain**: municipality (市区町村, keyed by the standard local government
  code), regional mesh (地域メッシュ), and census enumeration units depending on the
  table. First integration targets **municipality grain** (low geospatial complexity).
- **fields needed (first cut)**: total population, household count, age-band
  population (for youth ratio), daytime population where available.
- **access / key requirement**: REST API. **Requires free e-Stat user registration to
  obtain an application ID (appId)**; the appId is passed on every request. JSON,
  JSONP, XML, and CSV outputs are supported (API spec 3.0).
- **license / terms**: data is provided under the Japanese Government Standard Terms of
  Use (政府標準利用規約 第2.0版), which is **explicitly stated to be compatible with
  CC BY 4.0**. Attribution (credit display) is required.
- **refresh cadence**: depends on the statistic. The Population Census (国勢調査) is
  every 5 years; many tables update annually or more often. Record the survey year per
  table and surface it as a freshness signal.
- **caveats**: table and class-code selection is fiddly; regional code matching across
  tables must be handled carefully; some granular tables suppress small-count cells.
- **status**: **v1** — primary demand layer.

### Selected table for the first integration

- **Table family**: 国勢調査 令和2年国勢調査 「都道府県・市区町村別の主な結果」
  (2020 Population Census, main results by prefecture/municipality).
  - portal: `toukei=00200521`, `tstat=000001136464`; file listing
    `stat_infid=000032143614`.
- **Field selected**: total population (男女別人口の「総数」). Exactly one demand proxy
  for the first cut — no multi-table integration yet.
- **Category filter**: select the sex-total category (e.g. `@cat01=000`) so each ward
  has a single value. The ingestion script exposes this via `--cat-filter @cat01=000`.
- **Grain**: municipality; filtered to the Tokyo 23 special wards (codes 13101–13123).
- **Why this table**: official, credible, and joinable by municipality code with **no
  GIS pipeline** — the lowest-friction credible first integration.
- **`statsDataId` handling**: the live API `statsDataId` is **version-specific**, so it
  is **not hardcoded**. Pin it from the e-Stat table search and pass it via
  `ESTAT_STATS_DATA_ID` (see `.env.example`). The repo ships a schema fixture
  (`data/sample/estat_population_sample.json`) so the transform and tests run offline.
- **sample vs live provenance**: sample mode is for **schema validation only**, not
  real findings. It reads the fixture, labels rows `source_mode=sample_fixture`, and
  writes a **separate** `data/processed/estat_demand_tokyo23_sample.csv`. Live mode
  labels rows `source_mode=live_public` and writes `estat_demand_tokyo23.csv`. The
  dashboard treats a layer as real only when `source_mode == "live_public"`.
- **Caveats specific to this table**: total population is a coarse demand proxy
  (daytime population would refine it); census cycle is 5 years (carry the survey year
  as freshness); some small-area cells can be suppressed. This proxy says nothing about
  income, purchasing power, or actual demand.

### Daytime-activity layer (e-Stat 従業地・通学地集計, 昼間人口)

A **Demand-axis refinement** added on top of the resident-population Demand layer — same
provider (e-Stat), same survey (令和2年国勢調査), same municipality-code spine, same license.

- **Dataset**: 国勢調査 令和2年 **従業地・通学地集計**, table「常住地又は従業地・通学地別
  人口（夜間人口・昼間人口）－全国，都道府県，市区町村」.
- **Catalog / API**: getStatsData 3.0. **Pin the table id via `ESTAT_DAYTIME_STATS_DATA_ID`**
  (separate from the resident table's `ESTAT_STATS_DATA_ID`). Do not display or commit the
  statsDataId — find it from the e-Stat catalog page for the table named above.
- **Daytime cell (verified)**: category `cat01=180` = 従業地・通学地による人口_総数（昼間
  人口）; `cat01=100` is the nighttime/resident total. The codes are table-version specific
  (like the L01 keys) — confirm on the table. This table has no sex split (totals only), so
  the live filter is just `--cat-filter @cat01=180`.
- **Metric**: per-ward **daytime population** (昼間人口) → `daytime_activity_score` (min-max
  0..100). A **daytime / commuter-presence proxy** only — NOT demand, sales, revenue, or
  profit. People who neither work nor study are counted at residence, per the census
  definition.
- **Grain / join**: Tokyo 23 wards, municipality code (13101–13123) — joins directly to the
  resident Demand layer. License: 政府標準利用規約 第2.0版 (CC BY 4.0 compatible).
  Attribution: 出典：令和2年国勢調査（総務省統計局）従業地・通学地集計.
- **How it is used**: added to the Opportunity Score as a **positive Demand-axis term** with
  its own weight, **default 0** (baseline ranking unchanged). It does **not** count as a 5th
  coverage layer (it overlaps the resident Demand axis), so it never inflates the confidence
  label. An optional **display-only** `daytime_to_resident_ratio` (daytime ÷ resident) is
  approximate — it mixes two census tabulations whose population bases differ by <1%.
- **A2 deferred**: the official 昼夜間人口比率 table (`statdisp_id=0003454499`) is a candidate
  but is **not** fed into the score for now (a ratio over-weights tiny-resident central wards).
- **sample vs live**: sample reads `data/sample/estat_daytime_sample.json` (schema fixture;
  illustrative cat codes `@cat01=01`/`@cat02=000`), labels `sample_fixture`, writes
  `estat_daytime_tokyo23_sample.csv`. Live labels `live_public`, writes
  `estat_daytime_tokyo23.csv`. Reproduction: `docs/live_data_runbook.md`.

## 2. MLIT National Land Numerical Information (国土数値情報)

- **official URL**: https://nlftp.mlit.go.jp/ksj/index.html
- **provider**: Ministry of Land, Infrastructure, Transport and Tourism (MLIT).
- **intended use**: accessibility layer (railway stations, roads, administrative
  boundaries) and cost layer (official land prices / 地価公示).
- **geographic grain**: vector GIS geometry — points (stations, land-price points),
  lines (rail, roads), polygons (administrative boundaries). High geospatial complexity.
- **fields needed**: station point locations, administrative boundary polygons (to
  define the area grain), land-price point values for the cost proxy.
- **access / key requirement**: **no API** — bulk file download by category/year from
  the portal. Formats: Shapefile, GeoJSON, XML (JPGIS), plus legacy CSV/TXT.
- **license / terms**: most foundational datasets (topography, land use, public
  facilities, transport, land price, etc.) are **CC BY 4.0 compatible**, but **some
  datasets are non-commercial only** (e.g. certain heritage/tourism datasets) and a few
  have other terms. **The license must be checked per dataset and per version** — older
  versions can carry different terms.
- **refresh cadence**: dataset-dependent; many layers are updated on a yearly or
  multi-year basis. Land-price data is annual.
- **caveats**: shapefile/CRS handling adds setup complexity (GeoPandas/Shapely);
  coordinate reference systems must be normalized; file sizes are non-trivial.
- **status**: v1 sample / live-deferred (accessibility — GIS), v1 live-verified (cost —
  GIS-free) — adds the heavier geospatial pipeline.

### Selected dataset for accessibility (first integration)

- **Dataset**: 国土数値情報 **鉄道データ N02** — Station layer (駅).
- **Official URL**: https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N02-2022.html
- **Version**: 2022 (令和4年, base date 2022-12-31).
- **Formats**: GML (JPGIS2014), Shapefile, GeoJSON.
- **License / terms**: N02 from 2020 onward is **open data** under MLIT's applicable
  terms (CC BY compatible). Confirm per dataset/version. Attribution required:
  **出典：国土数値情報（鉄道データ N02）（国土交通省）**.
- **Attributes**: line (N02_003), operator (N02_004), station name (N02_005), station/
  group codes — **point geometry, no administrative-area code**.
- **Metric**: station **count per ward** + optional **per-capita** (`station_count_per_10k`)
  when the e-Stat population layer is present. A **station-access proxy** only — not
  demand or willingness to buy.
- **GIS constraint (important)**: because N02 stations carry no municipality code,
  assigning a station to a ward needs a **spatial join** (point-in-polygon vs. N03 ward
  boundaries) = GeoPandas/shapely. Per the minimal-first rule this GIS step is
  **deferred and not implemented**: `--mode live` stops with an opt-in proposal. The
  pure transform + sample fixture (features carry an injected `area_code`) exercise the
  full pipeline offline; sample writes a separate
  `data/processed/mlit_accessibility_tokyo23_sample.csv` labeled `source_mode=sample_fixture`.

### Selected dataset for cost pressure (first integration)

- **Dataset**: 国土数値情報 **地価公示データ L01** (standard-site land prices, 地価公示).
- **Official URL**: https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-L01-v3_1.html
- **Formats**: GML (JPGIS2014), Shapefile, GeoJSON.
- **License / terms**: L01 from 2020 onward is **open data** under MLIT's applicable
  terms (CC BY compatible); confirm per dataset/version. Attribution required:
  **出典：国土数値情報（地価公示データ L01）（国土交通省）**.
- **Key attributes**: each standard-site point carries an **administrative-area code**
  and the **published land price 円/m²**, plus address and land-use fields. **Attribute
  numbering varies by version**, so the parser's code/price keys are configurable —
  always confirm them against the actual download. **Verified keys (令和5年 / 2023
  version):** `--code-key L01_022` (行政区域コード, e.g. `13101`) and `--price-key L01_006`
  (当該年価格 円/m², matching the latest entry in the historical series `L01_101`). The
  module defaults (`L01_017` / `L01_019`) are **wrong for the 2023 version** (both decode
  to `'false'`). Reproduction details: `docs/live_data_runbook.md`.
- **Download (verified)**: `https://nlftp.mlit.go.jp/ksj/gml/data/L01/L01-23/L01-23_13_GML.zip`
  (東京都 = 13, 2023). The datalist page advertises only GML/Shapefile, but the zip
  **ships a `L01-23_13.geojson`** directly — **no format conversion / GIS dependency
  needed**; extract that one file and pass it to `--geojson`.
- **Metric**: per-ward **median** (and mean) published land price, with an
  `observation_count`. Used as `cost_pressure_score` (higher price → higher cost
  pressure, a **negative** factor in opportunity).
- **GIS (important)**: unlike N02 stations, L01 **carries the municipality code**, so
  aggregating to a ward is **GIS-free** (group by code) — no spatial join needed. Live
  ingestion parses a downloaded L01 GeoJSON by code.
- **Caveat**: published land price is a **cost-pressure proxy only** — NOT actual store
  rent, operating cost, or profit margin. Standard sites are sparse, so a ward median is
  a coarse signal; wards absent from the data are omitted, not zero.
- **sample vs live**: sample reads `data/sample/mlit_landprice_sample.json`, labels
  `source_mode=sample_fixture`, writes a separate
  `data/processed/mlit_cost_tokyo23_sample.csv`. Live labels `source_mode=live_public`
  and writes `mlit_cost_tokyo23.csv`.

## 3. Tokyo Open Data Catalog (東京都オープンデータカタログサイト)

- **official URL**: https://catalog.data.metro.tokyo.lg.jp/
- **provider**: Tokyo Metropolitan Government.
- **intended use**: Tokyo-specific supplements — local facilities, transport, and
  administrative datasets that enrich ward-level analysis.
- **geographic grain**: dataset-specific (ward, address, point, or aggregate).
- **fields needed**: selected per dataset; used to enrich, not anchor, core metrics.
- **access / key requirement**: CKAN-based portal with a data API; many datasets also
  offer direct CSV/HTML downloads. No global key for catalog browsing.
- **license / terms**: default **CC BY 4.0** for Tokyo-published datasets (confirm per
  dataset, since some are republished from other bodies).
- **refresh cadence**: varies widely across datasets; check each dataset's metadata.
- **caveats**: field schemas and update cadences are inconsistent across datasets;
  treat as supplementary rather than a single reliable spine.
- **status**: v1 / later — enrichment layer.

## 4. OpenStreetMap / Overpass API

- **official URL**: https://overpass-api.de/ (docs: https://dev.overpass-api.de/overpass-doc/en/);
  underlying project https://www.openstreetmap.org/
- **provider**: OpenStreetMap community; Overpass API public instances.
- **intended use**: commercial-density and competition layers — POIs such as
  restaurants, cafes, convenience stores, supermarkets, plus stations as a cross-check
  on the accessibility layer.
- **geographic grain**: node / way / relation with lat/lon. Medium geospatial
  complexity: points must be spatially joined to the chosen area grain.
- **fields needed**: POI coordinates and category tags (e.g. `amenity`, `shop`).
- **access / key requirement**: **no API key**, queried via Overpass QL. **Rate-limited
  / fair-use**: send queries serially (not in parallel) per host; the public servers
  queue requests and reject with **HTTP 429** when the queue/timeout is exceeded. Use a
  mirror and cache results locally; do not hammer the endpoint.
- **license / terms**: **ODbL (Open Database License)** — requires **attribution** and
  is **share-alike**. Display "© OpenStreetMap contributors". Small extractions may fall
  under fair use, but attribution should always be shown.
- **refresh cadence**: continuously edited; snapshot the extraction date and treat it as
  the freshness signal.
- **caveats**: **coverage and tagging quality vary by area and category** — this is the
  single most important caveat for the competition metric. POI completeness is uneven,
  so density must be treated as a proxy with an explicit coverage/confidence penalty.
- **status**: v1 — primary commercial/competition proxy.

### Selected category for the first integration

- **OSM tag**: `shop=convenience` (Japanese convenience stores / コンビニ). Chosen over
  `amenity=restaurant`/`cafe` because convenience-store tagging is dense and **stable**
  in Japan, giving a cleaner first-cut count with less tagging noise.
- **Metric**: POI **count per ward**, plus an optional **per-capita density**
  (`poi_per_10k`) when the e-Stat population layer is present. Treated as a
  **commercial-density / competition proxy** only — not demand, sales, or revenue.
- **Grain / join**: Tokyo 23 wards, keyed by the same municipality-code spine as the
  Demand layer. The spatial join is offloaded to the Overpass **area filter**
  (server-side, per ward), so no local GIS is needed for the first cut.
- **Access / rate limit**: queried per ward, **serially with a delay** between requests
  (`--sleep`, default 1s), each with an Overpass `timeout`. A 429 is surfaced as a
  back-off error. Use `--max-wards` for a small smoke test; cache results locally.
- **License / attribution**: **ODbL** (attribution + share-alike). Every output row
  carries `© OpenStreetMap contributors`, shown in the dashboard and CSV.
- **sample vs live provenance**: sample mode is for **schema validation only**. It reads
  `data/sample/osm_convenience_sample.json`, labels rows `source_mode=sample_fixture`,
  and writes a **separate** `data/processed/osm_competition_tokyo23_sample.csv`. Live
  mode labels rows `source_mode=live_public` and writes `osm_competition_tokyo23.csv`.
  The dashboard treats a layer as real only when `source_mode == "live_public"`.
- **caveats**: OSM coverage/tagging completeness is **uneven** — counts are a proxy with
  real coverage risk; near-boundary POIs may appear under two ward queries (de-duplicated
  by OSM id); wards absent from the response are omitted, not asserted as zero.

## 5. RESAS (Regional Economy and Society Analyzing System)

- **official URL**: https://resas.go.jp/
- **provider**: Cabinet Office / regional economy data initiative.
- **intended use**: optional regional economic and population-movement context.
- **access / key requirement**: API with an issued key; field availability needs
  verification before use.
- **license / terms**: verify current terms before integration.
- **status**: later (optional) — not required for v1.

## 6. GDELT

- **official URL**: https://www.gdeltproject.org/
- **provider**: The GDELT Project.
- **intended use**: phase-2 intelligence extension — news volume, event type, and tone
  as area/industry risk or attention signals.
- **access / key requirement**: public API / BigQuery dataset, no paid key.
- **caveats**: noisy; better suited to an intelligence extension than the MVP. Adds
  abstraction that is not needed for area prioritization.
- **status**: later (phase 2).

---

## Required metadata for every source

Before a source feeds a metric, ensure all of the following are recorded (the sections
above follow this template):

- official URL
- provider
- intended use
- geographic grain
- fields needed
- license / terms note
- refresh cadence if known
- caveats
- whether it is MVP / v1 / later

## Data-source quality questions

For each metric, ask:

1. Is this source official?
2. Is it recent enough for the decision?
3. Does the geography align with the dashboard grain?
4. Is the field a direct measure or a proxy?
5. How uneven is coverage across Tokyo?
6. How should missingness affect confidence?

## Integration order (real data)

Start with the synthetic dashboard, then integrate real sources in this order. The
order deliberately escalates geospatial difficulty so each step is independently
shippable. See `implementation_plan.md` for the full candidate comparison and the
selected first integration.

1. **Demand layer: e-Stat** at municipality grain — establishes the area-key spine.
2. **Commercial / competition layer: OSM / Overpass** POIs — adds spatial join.
3. **Accessibility layer: MLIT** station data (or OSM stations as a first proxy).
4. **Cost layer: MLIT** land-price data — heaviest geospatial pipeline.

## Important framing

Public data can support:

- area prioritization
- market structure understanding
- opportunity screening
- competition density proxy
- scenario analysis

Public data cannot prove:

- actual revenue
- unit economics
- conversion rate
- customer retention
- true competitor performance

## Sources verified (June 2026)

- e-Stat API portal: https://www.e-stat.go.jp/api/
- e-Stat API spec 3.0: https://www.e-stat.go.jp/api/api-info/e-stat-manual3-0
- Government Standard Terms of Use (CC BY 4.0 compatibility): https://ja.wikipedia.org/wiki/政府標準利用規約
- MLIT National Land Numerical Information: https://nlftp.mlit.go.jp/ksj/index.html
- Tokyo Open Data Catalog: https://catalog.data.metro.tokyo.lg.jp/
- Overpass API docs: https://dev.overpass-api.de/overpass-doc/en/
- OSM API usage policy: https://operations.osmfoundation.org/policies/api/
