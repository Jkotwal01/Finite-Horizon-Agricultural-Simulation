"""
test/test_warehouse.py — FR-012: Warehouse capacity and overflow.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from engine.warehouse import WarehouseManager
import config as cfg


@pytest.fixture
def wh():
    return WarehouseManager()


class TestFullShed:

    def test_add_within_capacity(self, wh):
        """Normal case: add units within 100-unit limit."""
        ok = wh.add_to_shed("WHEAT", 50)
        assert ok is True
        assert wh.get_shed("WHEAT") == 50

    def test_add_exactly_at_capacity(self, wh):
        """Adding exactly 100 units is accepted."""
        ok = wh.add_to_shed("WHEAT", 100)
        assert ok is True
        assert wh.total_non_seed_units() == 100

    def test_add_over_capacity_rejected(self, wh):
        """ST13-C: Adding beyond 100 units is rejected."""
        wh.add_to_shed("WHEAT", 90)
        ok = wh.add_to_shed("TOMATO", 15)  # would reach 105
        assert ok is False
        assert wh.total_non_seed_units() == 90

    def test_seeds_bypass_capacity(self, wh):
        """Seeds do NOT count toward the 100-unit limit."""
        wh.add_to_shed("WHEAT", 100)
        ok = wh.add_to_shed("WHEAT_SEED", 20)
        assert ok is True
        # total non-seed is still 100
        assert wh.total_non_seed_units() == 100

    def test_fertilizer_bypasses_capacity(self, wh):
        """FERTILIZER does not count toward shed capacity."""
        wh.add_to_shed("WHEAT", 100)
        ok = wh.add_to_shed("FERTILIZER", 10)
        assert ok is True

    def test_forecast_85_pct_load(self, wh):
        """ST13-A: 85 units → emergency_relief_needed = True."""
        wh.add_to_shed("WHEAT", 85)
        fc = wh.forecast()
        assert fc.emergency_relief_needed is True
        assert fc.relief_units_needed > 0

    def test_forecast_90_pct_load(self, wh):
        """ST13-B: 90 units → still flagged."""
        wh.add_to_shed("WHEAT", 90)
        fc = wh.forecast()
        assert fc.emergency_relief_needed is True

    def test_forecast_full(self, wh):
        """ST13-C: 100 units → overflow_risk = True."""
        wh.add_to_shed("WHEAT", 100)
        fc = wh.forecast()
        assert fc.overflow_risk is True

    def test_forecast_projected_inflow(self, wh):
        """Projected total with incoming harvest."""
        wh.add_to_shed("WHEAT", 50)
        fc = wh.forecast(projected_inflow=30, projected_outflow=0)
        assert fc.projected_total == 80

    def test_remove_from_shed(self, wh):
        wh.add_to_shed("WHEAT", 20)
        ok = wh.remove_from_shed("WHEAT", 10)
        assert ok is True
        assert wh.get_shed("WHEAT") == 10

    def test_remove_insufficient_fails(self, wh):
        wh.add_to_shed("WHEAT", 5)
        ok = wh.remove_from_shed("WHEAT", 10)
        assert ok is False

    def test_worker_carrying_counts_toward_total(self, wh):
        """Carried goods DO count toward total physical inventory."""
        wh.add_to_shed("WHEAT", 50)
        wh.add_to_worker(0, "TOMATO", 10)
        assert wh.total_non_seed_units() == 60
