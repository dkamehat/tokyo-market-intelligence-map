"""Unit tests for the e-Stat demand-layer transform and client config.

These tests never touch the network and pass without ESTAT_APP_ID set.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tokyo_market_intel.ingestion.estat_population import (
    SOURCE_MODE_LIVE,
    SOURCE_MODE_SAMPLE,
    TOKYO_23_WARDS,
    build_demand_layer,
    check_result_status,
    classify_demand_layer,
    extract_area_values,
)
from tokyo_market_intel.sources.estat import (
    APP_ID_ENV,
    EstatApiError,
    EstatConfigError,
    get_app_id,
    redact,
)

_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "sample"
SAMPLE_PATH = _DATA_DIR / "estat_population_sample.json"
TOTAL_FILTER = {"@cat01": "000"}


@pytest.fixture
def payload() -> dict:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def test_sample_fixture_exists_and_has_success_status(payload: dict) -> None:
    check_result_status(payload)  # must not raise


def test_extract_area_values_with_total_filter(payload: dict) -> None:
    frame = extract_area_values(payload, value_filter=TOTAL_FILTER)
    # 6 Tokyo wards + 1 non-Tokyo area, one row each after filtering to total.
    assert len(frame) == 7
    assert frame["value"].notna().all()
    chiyoda = frame.loc[frame["area_code"] == "13101", "value"].iloc[0]
    assert chiyoda == 66680


def test_extract_area_values_without_filter_is_ambiguous(payload: dict) -> None:
    # Without a category filter, each area has total/male/female -> ambiguous.
    with pytest.raises(EstatApiError, match="value_filter"):
        extract_area_values(payload)


def test_non_numeric_values_become_nan() -> None:
    payload = {
        "GET_STATS_DATA": {
            "RESULT": {"STATUS": 0},
            "STATISTICAL_DATA": {
                "DATA_INF": {
                    "VALUE": [
                        {"@cat01": "000", "@area": "13101", "$": "-"},
                        {"@cat01": "000", "@area": "13102", "$": "169179"},
                    ]
                }
            },
        }
    }
    frame = extract_area_values(payload, value_filter=TOTAL_FILTER)
    assert frame.loc[frame["area_code"] == "13101", "value"].isna().all()
    assert frame.loc[frame["area_code"] == "13102", "value"].iloc[0] == 169179


def test_build_demand_layer_keeps_only_23_wards_and_scores(payload: dict) -> None:
    # Build as live to exercise the real-data labeling path.
    demand = build_demand_layer(payload, value_filter=TOTAL_FILTER, source_mode=SOURCE_MODE_LIVE)

    # Yokohama (14100) must be dropped; only Tokyo wards remain.
    assert set(demand["area_code"]).issubset(TOKYO_23_WARDS.keys())
    assert "14100" not in set(demand["area_code"])
    assert len(demand) == 6

    assert list(demand.columns) == [
        "area",
        "area_code",
        "population",
        "demand_score",
        "source_mode",
        "data_basis",
    ]

    # demand_score is min-max scaled 0..100 and sorted descending.
    assert demand["demand_score"].max() == pytest.approx(100.0)
    assert demand["demand_score"].min() == pytest.approx(0.0)
    assert demand["demand_score"].is_monotonic_decreasing

    # Highest population ward (Shinjuku, 349385) ranks first.
    assert demand.iloc[0]["area"] == "Shinjuku"
    assert demand.iloc[-1]["area"] == "Chiyoda"


def test_live_build_is_labeled_live_public(payload: dict) -> None:
    demand = build_demand_layer(payload, value_filter=TOTAL_FILTER, source_mode=SOURCE_MODE_LIVE)
    assert (demand["source_mode"] == SOURCE_MODE_LIVE).all()
    assert demand["data_basis"].str.startswith("public:e-Stat").all()
    assert classify_demand_layer(demand) == "live_public"


def test_sample_build_is_labeled_sample_and_never_real(payload: dict) -> None:
    # Default source_mode is the conservative sample mode; build from the fixture.
    demand = build_demand_layer(payload, value_filter=TOTAL_FILTER)
    assert (demand["source_mode"] == SOURCE_MODE_SAMPLE).all()
    assert demand["data_basis"].str.startswith("sample fixture").all()
    assert not demand["data_basis"].str.startswith("public:").any()
    # The key safety guarantee: sample output is NOT classified as real public data.
    assert classify_demand_layer(demand) == "sample_fixture"
    assert classify_demand_layer(demand) != "live_public"


def test_build_demand_layer_rejects_unknown_source_mode(payload: dict) -> None:
    with pytest.raises(ValueError, match="source_mode"):
        build_demand_layer(payload, value_filter=TOTAL_FILTER, source_mode="totally-real")


def test_classify_demand_layer_missing_and_unknown() -> None:
    assert classify_demand_layer(None) == "missing"
    assert classify_demand_layer(pd.DataFrame()) == "missing"
    # A frame without source_mode (e.g. a stale/older file) is treated as not real.
    no_mode = pd.DataFrame({"area": ["Chiyoda"], "population": [1]})
    assert classify_demand_layer(no_mode) == "unknown"


def test_check_result_status_raises_on_error_payload() -> None:
    payload = {
        "GET_STATS_DATA": {
            "RESULT": {"STATUS": 100, "ERROR_MSG": "該当データはありません。"}
        }
    }
    with pytest.raises(EstatApiError, match="status 100"):
        check_result_status(payload)


def test_get_app_id_missing_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(APP_ID_ENV, raising=False)
    with pytest.raises(EstatConfigError, match=APP_ID_ENV):
        get_app_id()


def test_redact_masks_the_app_id() -> None:
    secret = "super-secret-app-id"
    text = f"failed for appId={secret} oops"
    masked = redact(text, app_id=secret)
    assert secret not in masked
    assert "***REDACTED***" in masked
