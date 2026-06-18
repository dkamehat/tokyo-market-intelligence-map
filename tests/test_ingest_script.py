"""Tests for the thin ingestion CLI layer.

Focus on the security-relevant default (sample unless ESTAT_APP_ID is set) and the
argument parser's error path. No network access.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from tokyo_market_intel.sources.estat import APP_ID_ENV

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ingest_estat_population.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("ingest_estat_population", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


script = _load_script()


def test_resolve_mode_respects_explicit_choice() -> None:
    assert script.resolve_mode("sample") == "sample"
    assert script.resolve_mode("live") == "live"


def test_resolve_mode_auto_defaults_to_sample_without_app_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(APP_ID_ENV, raising=False)
    assert script.resolve_mode("auto") == "sample"


def test_resolve_mode_auto_selects_live_with_app_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(APP_ID_ENV, "dummy-value")
    assert script.resolve_mode("auto") == "live"


def test_parse_cat_filters_parses_pairs() -> None:
    assert script.parse_cat_filters(["@cat01=000", "@cat02=001"]) == {
        "@cat01": "000",
        "@cat02": "001",
    }


def test_parse_cat_filters_rejects_bad_input() -> None:
    with pytest.raises(SystemExit):
        script.parse_cat_filters(["no-equals-sign"])
