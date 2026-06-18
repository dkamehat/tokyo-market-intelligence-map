# Portfolio Positioning

## English resume bullet

Built a public-data Market Intelligence BI product for Tokyo that ranks commercial opportunity areas by combining demographic, accessibility, commercial-density, competition, cost, and data-quality signals. Designed the system as a scenario-driven decision tool with explicit confidence and proxy-risk handling, not a static dashboard.

## Japanese resume bullet

東京の商業機会を公開データのみで評価する Market Intelligence BI プロダクトを構築。人口・交通利便性・商業密度・競合・コスト・データ品質を統合し、シナリオ別の優先エリアランキングと信頼度を提示する意思決定支援ダッシュボードとして設計。

## 30-second interview explanation

This project answers a simple question: which Tokyo areas should a consumer business prioritize for expansion, marketing, or micro-fulfillment? I used only public data and designed a scoring system that combines demand proxies, accessibility, competition, cost, and data-quality signals. On top of the integrated Opportunity Score I wrote a **live-backed decision memo** (`docs/decision_memo_tokyo.md`) that turns the live result into a concrete, caveated recommendation — currently Setagaya / Nerima / Ota as top screening candidates at **Medium confidence** (Demand + Cost live). I also added a live **daytime-activity layer** (昼間人口) as a tunable Demand-axis refinement, so a reviewer can see the resident-vs-commuter trade-off shift the ranking (central business wards rise when daytime presence is weighted) without overstating confidence. **Scenario presets** (Residential baseline / Daytime activity / Cost-sensitive / Custom) let a stakeholder switch the resident-vs-daytime hypothesis as a decision lens — sensitivity analysis, not a change to the data or its confidence. A third layer (OSM competition) is implemented and smoke-tested, but its full live run remains **pending on an observed public Overpass endpoint reliability / availability issue** (429/504); the sample transform and a 1-ward smoke test passed, so it is treated as a backlog item to retry off-peak. The key point is not just visualization; the dashboard shows how recommendations change under different strategic scenarios and makes uncertainty explicit.

## 2-minute technical explanation

I structured the project as a small decision-intelligence product. Public data is ingested into a reproducible analytical layer, transformed into documented metric groups, then exposed through a dashboard and decision memo. The main opportunity score combines demand, accessibility, growth, competition, cost, and uncertainty penalties. Each metric is treated as a proxy, so the system includes confidence labels and caveats. This keeps the recommendation useful while avoiding false precision from public data. With internal data such as orders, conversion rate, delivery SLA, CAC, LTV, and unit economics, the model could evolve from opportunity scoring to revenue impact estimation.

## Risk / limitation explanation

The main limitation is that public data cannot prove actual customer demand or revenue. Population, POIs, stations, and land price are proxy signals. OSM coverage can be uneven, demographic data can lag, and geographic grains may not align perfectly. I handle this by separating opportunity score from confidence, documenting data lineage, and showing what internal data would be needed to validate the result.

## Why this is BI / Intelligence, not only BizOps

This project is not a strategy recommendation deck. It is a BI / Intelligence system that defines metrics, documents source lineage, normalizes public data, exposes assumptions, and supports scenario-based decision-making. The output helps stakeholders decide, but the core artifact is the data product and metric architecture.
