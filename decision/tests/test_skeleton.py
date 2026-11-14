"""Smoke tests for the skeleton only (not rules): config loads, texts render, failing closed."""

import pytest
from builders import NOW, codes, make_mandate, make_request
from trade_contracts import ReasonCode

from trade_decision import DecisionConfig, decide, load_config
from trade_decision.texts import eur, render


def test_config_loads_and_is_frozen():
    cfg = load_config()
    assert cfg.default_order_limit_cents == 50000 and cfg.timezone == "Europe/Helsinki"
    with pytest.raises(AttributeError):
        cfg.max_alternatives = 5  # type: ignore[misc]


def test_config_rejects_unknown_keys(tmp_path):
    bad = tmp_path / "c.yaml"
    bad.write_text("surprise: 1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(bad)


def test_money_text_and_template_render():
    assert eur(140000) == "EUR 1,400.00"
    message, fix = render(ReasonCode.SPEND_OVER_LIMIT, {"total_cents": 140000, "limit_cents": 50000})
    assert "EUR 1,400.00" in message and "EUR 500.00" in message and fix


def test_engine_fails_closed_never_auto():
    # malformed input (lines=None) makes the engine raise internally -> ASK_HUMAN / ENGINE_ERROR
    d = decide(make_request(), make_mandate(), None, [], [], now=NOW)  # type: ignore[arg-type]
    assert d.outcome == "ASK_HUMAN" and codes(d) == ["ENGINE_ERROR"]


def test_malformed_request_still_returns_a_decision():
    d = decide(None, None, [], [], [], now=NOW)  # type: ignore[arg-type]
    assert d.outcome == "ASK_HUMAN" and d.request_id == "unknown"


def test_decision_config_defaults_match_yaml():
    assert load_config() == DecisionConfig()


def test_builders_make_valid_contract_objects():
    assert make_request().needed_by.isoformat() == "2026-11-16"
