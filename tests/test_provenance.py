"""Tests for the shared provenance classifier."""

from __future__ import annotations

import pandas as pd

from tokyo_market_intel.ingestion.provenance import (
    SOURCE_MODE_LIVE,
    SOURCE_MODE_SAMPLE,
    classify_layer,
)


def test_none_and_empty_are_missing() -> None:
    assert classify_layer(None) == "missing"
    assert classify_layer(pd.DataFrame()) == "missing"


def test_all_live_public() -> None:
    df = pd.DataFrame({"source_mode": [SOURCE_MODE_LIVE, SOURCE_MODE_LIVE]})
    assert classify_layer(df) == "live_public"


def test_all_sample_fixture() -> None:
    df = pd.DataFrame({"source_mode": [SOURCE_MODE_SAMPLE, SOURCE_MODE_SAMPLE]})
    assert classify_layer(df) == "sample_fixture"


def test_missing_column_is_unknown() -> None:
    df = pd.DataFrame({"area": ["Chiyoda"], "value": [1]})
    assert classify_layer(df) == "unknown"


def test_mixed_modes_is_unknown() -> None:
    df = pd.DataFrame({"source_mode": [SOURCE_MODE_LIVE, SOURCE_MODE_SAMPLE]})
    assert classify_layer(df) == "unknown"


def test_unrecognized_mode_is_unknown() -> None:
    df = pd.DataFrame({"source_mode": ["totally-real", "totally-real"]})
    assert classify_layer(df) == "unknown"


def test_custom_source_mode_column() -> None:
    df = pd.DataFrame({"prov": [SOURCE_MODE_LIVE]})
    assert classify_layer(df, source_mode_column="prov") == "live_public"
