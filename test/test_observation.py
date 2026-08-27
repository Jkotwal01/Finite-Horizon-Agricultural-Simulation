"""
test/test_observation.py — FR-001: Observation normalization tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from engine.observation import ObservationAdapter
from models.state import CanonicalState


@pytest.fixture
def adapter():
    return ObservationAdapter()


def make_raw(turn=0, cash=500.0, farms=None):
    if farms is None:
        farms = [{"row": 0, "col": 0, "status": "EMPTY"}]
    return {"turn": turn, "cash": cash, "farms": farms, "market": {}}


class TestObservationNormalization:

    def test_required_keys_present(self, adapter):
        """ST03-A: Normal case — all required keys produce CanonicalState."""
        raw = make_raw()
        state = adapter.normalise(raw)
        assert isinstance(state, CanonicalState)

    def test_missing_key_raises(self, adapter):
        """ST03-C: Missing required key raises ValueError."""
        with pytest.raises(ValueError, match="missing required keys"):
            adapter.normalise({"turn": 0})  # missing cash, farms, market

    def test_turn_normalised_to_int(self, adapter):
        """Types are normalised: turn must be int."""
        raw = make_raw(turn="5")  # string input
        state = adapter.normalise(raw)
        assert state.turn == 5
        assert isinstance(state.turn, int)

    def test_cash_normalised_to_float(self, adapter):
        raw = make_raw(cash="1000")
        state = adapter.normalise(raw)
        assert state.cash == 1000.0
        assert isinstance(state.cash, float)

    def test_day_hour_derived_correctly(self, adapter):
        """Turn 25 → day=1, hour=1 (24 turns/day)."""
        raw = make_raw(turn=25)
        state = adapter.normalise(raw)
        assert state.day == 1
        assert state.hour == 1

    def test_farms_normalised(self, adapter):
        raw = make_raw(farms=[{"row": "2", "col": "3", "status": "GROWING"}])
        state = adapter.normalise(raw)
        assert state.farms[0]["row"] == 2
        assert state.farms[0]["col"] == 3

    def test_market_normalised(self, adapter):
        raw = {
            "turn": 0, "cash": 100.0,
            "farms": [{"row": 0, "col": 0, "status": "EMPTY"}],
            "market": {"WHEAT": {"price": "8.5", "inventory": "10"}},
        }
        state = adapter.normalise(raw)
        assert state.market["WHEAT"]["price"] == 8.5
        assert isinstance(state.market["WHEAT"]["price"], float)

    def test_rules_snapshot_populated(self, adapter):
        raw = make_raw()
        state = adapter.normalise(raw)
        assert "total_turns" in state.rules
        assert state.rules["total_turns"] == 720

    def test_no_strategy_in_normalise(self, adapter):
        """Observation adapter must not modify market prices or make decisions."""
        raw = make_raw()
        state = adapter.normalise(raw)
        # No farms with non-EMPTY status injected by adapter
        for farm in state.farms:
            assert "strategy" not in farm
