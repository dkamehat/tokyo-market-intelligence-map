# Live Data Reproduction Runbook

This runbook records the **exact, reproducible steps and observed results** for the
public-data layers that have been run in live mode, so a reviewer can regenerate the real
findings without re-discovering version-specific details.

It captures what is *not* derivable from the code alone: the verified e-Stat live result,
the MLIT L01 download URL + version-specific property keys, and the integrated Opportunity
live result.

> Secrets and generated data are **never committed**: `.env`, `data/raw/*`, and
> `data/processed/*.csv` are gitignored. This runbook records *how* to regenerate them, not
> their contents.

Reproduced and verified: **June 2026** (data: e-Stat 2020 Population Census; MLIT L01 2023 /
令和5年).

---

## 1. e-Stat Demand (live)

- **Credentials handling:** the e-Stat application ID (`ESTAT_APP_ID`) is kept in `.env` /
  the environment only. Its value is **never displayed and never committed**. The
  version-specific `ESTAT_STATS_DATA_ID` is likewise stored in `.env`; it may be kept out
  of logs as well.
- **Command:**

  ```bash
  cp .env.example .env   # fill ESTAT_APP_ID and ESTAT_STATS_DATA_ID (never commit .env)
  # load the vars into the shell, then:
  python scripts/ingest_estat_population.py --mode live --cat-filter @cat01=000
  ```

- **Live result (verified):** (2020 Population Census / 令和2年国勢調査, total population)
  - 23 wards (codes 13101–13123)
  - every row `source_mode = live_public`
  - Demand layer is shown as **REAL** in the dashboard
  - output: `data/processed/estat_demand_tokyo23.csv`

- **Do not commit:** `ESTAT_APP_ID`, `ESTAT_STATS_DATA_ID`, or
  `data/processed/estat_demand_tokyo23.csv`.

---

## 1b. e-Stat Daytime activity (live) — 昼間人口

A Demand-axis refinement (daytime population) from the same 2020 Census.

- **Table (verified)**: 従業地・通学地集計「常住地又は従業地・通学地別人口（夜間人口・昼間
  人口）（市区町村）」. **Pin its statsDataId via `ESTAT_DAYTIME_STATS_DATA_ID`** (separate
  from `ESTAT_STATS_DATA_ID`; kept in `.env`, never displayed or committed).
- **Category cell (verified)**: `cat01=180` = 従業地・通学地による人口_総数（昼間人口）;
  `cat01=100` is the nighttime/resident total. No sex split in this table, so the live filter
  is just `--cat-filter @cat01=180`. Codes are table-version specific — confirm via
  `getMetaInfo` before trusting a run.
- **Command:**

  ```bash
  # ESTAT_APP_ID + ESTAT_DAYTIME_STATS_DATA_ID in .env (never committed), then:
  python scripts/ingest_estat_daytime.py --mode live --cat-filter @cat01=180
  ```

- **Live result (verified, June 2026):**
  - 23 wards, every row `source_mode = live_public`
  - top daytime population: Minato 972,673 · Chiyoda 903,780 · Setagaya 854,838
  - day/night ratio contrast: Chiyoda ~13.5×, Minato ~3.7× vs. Setagaya ~0.9× (bedroom ward)
  - output: `data/processed/estat_daytime_tokyo23.csv`
  - cross-check: this table's nighttime total (cat01=100) for Chiyoda is 66,680, matching the
    resident layer (66,758) to <0.7% — confirming `cat01=180` is the matching daytime total.

- **Effect on Opportunity:** integrated as a positive Demand-axis term with **default weight
  0** (baseline ranking unchanged); raising the daytime weight to 1.0 re-ranks central wards
  up (Chiyoda 23→17, Minato 21→11), confidence stays Medium (not a coverage layer).
- **Framing:** daytime population is a **daytime-activity proxy** — not demand, sales, or
  revenue.
- **Do not commit:** `ESTAT_DAYTIME_STATS_DATA_ID`, `data/raw/estat_daytime_raw.json`, or
  `data/processed/estat_daytime_tokyo23.csv`.

---

## 2. MLIT L01 Cost pressure (live)

- **Source file used:**
  - URL: `https://nlftp.mlit.go.jp/ksj/gml/data/L01/L01-23/L01-23_13_GML.zip`
  - 東京都 = prefecture code **13**, **令和5年 / 2023** version (base date 2023-01-01).
- **GeoJSON is shipped inside the zip.** The L01 datalist page only advertises GML and
  Shapefile, but the downloaded `L01-23_13_GML.zip` **contains `L01-23_13.geojson`**
  directly — so **no format conversion and no GIS dependency is needed**. Extract that one
  file:

  ```bash
  # extract just the GeoJSON into data/raw/ (gitignored)
  unzip -o -j data/raw/L01-23_13_GML.zip "L01-23_13_GML/L01-23_13.geojson" -d data/raw/
  ```

- **Property keys are version-dependent — confirm against the real file.** For the **2023**
  version the parser defaults (`L01_017` / `L01_019`) are **wrong** (both decode to the
  string `'false'`). The correct keys for this version are:
  - `--code-key L01_022` — 行政区域コード (e.g. `13101`)
  - `--price-key L01_006` — 当該年価格 / current-year land price in 円/m² (matches the latest
    entry in the historical price series `L01_101`)

  Always verify the keys on the actual download before trusting a live run (scan a feature's
  `properties` for the 5-digit `13xxx` admin code and the current-year price), because MLIT
  renumbers L01 attributes across versions.

- **Command:**

  ```bash
  python scripts/ingest_mlit_cost.py --mode live \
    --geojson data/raw/L01-23_13.geojson \
    --code-key L01_022 --price-key L01_006
  ```

- **Live result (verified):**
  - 23 rows, every row `source_mode = live_public`
  - columns: `land_price_median`, `land_price_mean`, `observation_count`,
    `cost_pressure_score`
  - highest cost pressure: **Chiyoda** (千代田); lowest: **Adachi** (足立)
  - output: `data/processed/mlit_cost_tokyo23.csv`
  - 2,602 features in the file; 1,594 standard-site points fall inside the 23 wards (the
    remainder are Tama-area municipalities the transform filters out). Per-ward
    `observation_count` ranges widely (e.g. ~24 in Sumida vs ~143 in Setagaya), so a ward
    median is coarse where the count is low — that column exposes it.

- **Important framing:** published land price is a **cost-pressure proxy only** — it is
  **not** actual store rent, operating cost, or profit margin.
- **Do not commit:** `data/raw/*` (the zip and extracted GeoJSON) or
  `data/processed/mlit_cost_tokyo23.csv`.

---

## 2b. Competition (OSM / Overpass) — live attempt (pending)

Competition is **not live-verified yet** — kept here for reproducibility.

- **Command:** `python scripts/ingest_osm_competition.py --mode live --sleep 5` (per-ward,
  serial, throttled; ODbL — outputs carry `© OpenStreetMap contributors`).
- **Observed (June 2026):** the 1-ward smoke test (`--max-wards 1`) **succeeded**
  (Chiyoda, `live_public`, attribution present). The **full 23-ward run failed** on the
  public Overpass endpoint — **HTTP 429** (rate-limited), and after a ~12-minute cooldown a
  retry hit **HTTP 504** (gateway timeout). Per the fair-use policy we did **not** hammer with
  repeated retries.
- **No partial file retained:** any incomplete `osm_competition_tokyo23.csv` was removed so
  Competition stays cleanly **not live** (a 1-ward file must never be treated as a real layer).
- **Status:** backlog — retry off-peak (a different time of day / Overpass mirror). This is an
  observed public Overpass endpoint reliability / availability issue; the sample transform and
  the 1-ward smoke test passed, but the full live run remains pending.
- **Do not commit:** `data/processed/osm_competition_tokyo23.csv`.

---

## 3. Opportunity integration (live)

- **Command:**

  ```bash
  python scripts/build_opportunity_layer.py --mode live
  ```

- **Live result (verified):**
  - **live layer count = 2** — Demand (e-Stat) + Cost (MLIT L01)
  - clears `MIN_LIVE_LAYERS_FOR_REAL` (= 2) → writes a **REAL** ranking
  - output: `data/processed/opportunity_tokyo23.csv`
  - `confidence_label = Medium` for all 23 wards (live == 2 and all contributing layers are
    live)
  - `missing_layer_count = 2` — Accessibility and Competition are not yet live
  - ranking top: **Setagaya (世田谷), Nerima (練馬), Ota (大田)**; bottom: **Chiyoda (千代田)**

- **Interpretation (state this in any memo built on it):**
  - The current REAL ranking is driven mainly by two axes: **Demand (+)** and **Cost
    pressure (−)**.
  - Accessibility and Competition are **not live**, so they are **neutral-filled at 50** and
    reflected in the **data-uncertainty penalty** — this does not change the relative order
    (a constant offset across all wards) but inflates the absolute score, which is exactly
    what the penalty and the Medium confidence flag.
  - This is **public-data screening**, not a revenue, actual-demand, or profitability
    forecast.

- **Do not commit:** `data/processed/opportunity_tokyo23.csv`.

---

## Reproduction checklist

- [ ] `.env` filled locally (never committed)
- [ ] e-Stat live run → `estat_demand_tokyo23.csv`, 23 wards, `live_public`
- [ ] L01 zip downloaded to `data/raw/`, GeoJSON extracted
- [ ] L01 keys verified against the actual file (`L01_022` / `L01_006` for the 2023 version)
- [ ] L01 live run → `mlit_cost_tokyo23.csv`, 23 rows, `live_public`
- [ ] Opportunity live build → `opportunity_tokyo23.csv`, 2 live layers, Medium confidence
- [ ] `git status` clean — no `.env`, `data/raw/*`, or `data/processed/*.csv` staged
