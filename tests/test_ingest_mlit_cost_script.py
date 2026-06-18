"""Tests for the MLIT cost ingestion CLI layer (no network)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ingest_mlit_cost.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("ingest_mlit_cost", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


script = _load_script()


def test_resolve_mode_auto_defaults_to_sample() -> None:
    assert script.resolve_mode("auto") == "sample"


def test_resolve_mode_respects_explicit_choice() -> None:
    assert script.resolve_mode("sample") == "sample"
    assert script.resolve_mode("live") == "live"


def test_live_without_geojson_errors() -> None:
    # Live needs a downloaded L01 file; without --geojson it exits 2 (no crash).
    assert script.main(["--mode", "live"]) == 2


def test_sample_mode_writes_output(tmp_path: Path) -> None:
    out = tmp_path / "cost.csv"
    rc = script.main(["--mode", "sample", "--out", str(out)])
    assert rc == 0
    assert out.exists()
