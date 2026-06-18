"""Tests for the opportunity build CLI layer (no real files)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_opportunity_layer.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("build_opportunity_layer", _SCRIPT)
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


def test_load_layers_handles_missing_files(tmp_path: Path) -> None:
    keys = ("demand", "accessibility", "competition", "cost")
    files = {key: tmp_path / f"{key}.csv" for key in keys}
    layers = script.load_layers(files)
    assert set(layers) == set(files)
    assert all(value is None for value in layers.values())
