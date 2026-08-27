"""
test/test_horizon.py — FR-002: Time and horizon boundary tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from models.state import TimeState


class TestHorizonBoundaries:

    def test_turn_zero(self):
        """ST02-A: Turn 0 → day 0, hour 0, remaining = 720."""
        ts = TimeState.from_turn(0)
        assert ts.turn == 0
        assert ts.day == 0
        assert ts.hour == 0
        assert ts.remaining_turns == 720
        assert not ts.is_endgame
        assert not ts.is_final_turn

    def test_mid_horizon(self):
        """Turn 360 is day 15, hour 0."""
        ts = TimeState.from_turn(360)
        assert ts.day == 15
        assert ts.hour == 0
        assert ts.remaining_turns == 360

    def test_endgame_threshold(self):
        """Turn 670 activates endgame mode."""
        ts = TimeState.from_turn(670)
        assert ts.is_endgame is True

    def test_before_endgame(self):
        """Turn 669 is NOT endgame."""
        ts = TimeState.from_turn(669)
        assert ts.is_endgame is False

    def test_final_turn(self):
        """Turn 719 is the final turn."""
        ts = TimeState.from_turn(719)
        assert ts.is_final_turn is True
        assert ts.remaining_turns == 1

    def test_remaining_never_negative(self):
        """ST02-C: remaining_turns must never go negative (boundary)."""
        ts = TimeState.from_turn(720)
        assert ts.remaining_turns == 0

        ts_over = TimeState.from_turn(800)
        assert ts_over.remaining_turns == 0

    def test_boundary_day_24(self):
        """Turn 24 starts day 1."""
        ts = TimeState.from_turn(24)
        assert ts.day == 1
        assert ts.hour == 0

    def test_hour_wraps_correctly(self):
        """Turn 25 → hour=1 within day 1."""
        ts = TimeState.from_turn(25)
        assert ts.day == 1
        assert ts.hour == 1
