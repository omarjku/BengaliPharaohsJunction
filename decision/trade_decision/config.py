"""Thresholds: YAML -> frozen dataclass (D19). Rule logic stays in code."""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

import yaml

RULES_VERSION = "t06-0.1"
DEFAULT_CONFIG_PATH = Path(__file__).with_name("default_config.yaml")


@dataclass(frozen=True)
class DecisionConfig:
    default_order_limit_cents: int = 50000
    price_change_tolerance_pct: float = 5.0
    # D7 (fixed in T06.1): only these exact stock values are Valio's "unknown" placeholder (Terminal
    # reports 999999). Any other big number (Eila's 9,999,999,999) is real "plenty", not unknown.
    unknown_quantity_sentinels: tuple[int, ...] = (999999,)
    suspicious_quantity: float = 100000
    min_reliability: float = 0.8
    reliability_missing_ask_above_cents: int = 20000
    quote_max_age_seconds: int = 900
    partial_preselect_coverage: float = 0.95
    max_alternatives: int = 3
    timezone: str = "Europe/Helsinki"
    low_confidence_threshold: float = 0.8


def load_config(path: str | Path | None = None) -> DecisionConfig:
    """Load thresholds from YAML; unknown keys are an error (closed vocabulary)."""
    data = yaml.safe_load(Path(path or DEFAULT_CONFIG_PATH).read_text(encoding="utf-8")) or {}
    unknown = set(data) - {f.name for f in fields(DecisionConfig)}
    if unknown:
        raise ValueError(f"unknown config keys: {sorted(unknown)}")
    if isinstance(data.get("unknown_quantity_sentinels"), list):
        data["unknown_quantity_sentinels"] = tuple(data["unknown_quantity_sentinels"])
    return DecisionConfig(**data)
