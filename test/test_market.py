"""
test/test_market.py — FR-013, FR-014: Market pricing and demand events.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from engine.market import MarketEngine
import config as cfg


@pytest.fixture
def engine():
    e = MarketEngine()
    e.reset_turn()
    return e


class TestUnitPriceCurve:

    def test_first_unit_at_base_price(self, engine):
        """ST14-A: First unit sold gets base price."""
        price = engine.marginal_price("WHEAT", unit_index=0, base_price=8.0)
        assert price == 8.0

    def test_price_decays_per_unit(self, engine):
        """BR-005: Each additional unit reduces price by DECAY amount."""
        p0 = engine.marginal_price("WHEAT", 0, 8.0)
        p1 = engine.marginal_price("WHEAT", 1, 8.0)
        assert p1 == p0 - cfg.MARKET_DECAY_PER_UNIT

    def test_price_floor_respected(self, engine):
        """Price never drops below PRICE_FLOOR ($1)."""
        # After many units, price should floor at $1
        price = engine.marginal_price("WHEAT", unit_index=100, base_price=8.0)
        assert price >= cfg.PRICE_FLOOR

    def test_multi_unit_proceeds(self, engine):
        """ST14-B: Total proceeds for 3 units uses marginal pricing."""
        total = engine.calculate_proceeds("WHEAT", 3, base_price=8.0)
        expected = 8.0 + 7.5 + 7.0  # 8 - 0.5*0, 8 - 0.5*1, 8 - 0.5*2
        assert abs(total - expected) < 0.01

    def test_max_orders_enforced(self, engine):
        """ST14-D: Order limit: plan allows at most MAX_ORDERS sell actions."""
        inventory = {f"PRODUCT_{i}": 10 for i in range(20)}
        plan = engine.plan_sales(inventory, market_prices={}, warehouse_emergency=False)
        assert plan.order_count <= cfg.MAX_ORDERS

    def test_emergency_triggers_sell(self, engine):
        """ST14-C: Warehouse emergency → sell regardless of price."""
        inventory = {"WHEAT": 5}
        plan = engine.plan_sales(inventory, {"WHEAT": 8.0}, warehouse_emergency=True)
        assert plan.order_count >= 1
        assert plan.reason == "EMERGENCY"

    def test_seeds_not_sellable(self, engine):
        """Seeds cannot appear in sell plan."""
        inventory = {"WHEAT_SEED": 10, "FERTILIZER": 5}
        plan = engine.plan_sales(inventory, {}, warehouse_emergency=False)
        for action in plan.sell_actions:
            assert not action["product"].endswith("_SEED")
            assert action["product"] != "FERTILIZER"

    def test_endgame_sell_all(self, engine):
        """Endgame mode forces liquidation of all inventory."""
        inventory = {"WHEAT": 3, "TOMATO": 2}
        plan = engine.plan_sales(inventory, {"WHEAT": 8.0, "TOMATO": 10.0},
                                 is_endgame=True)
        assert plan.order_count >= 1
        assert plan.reason == "ENDGAME"


class TestDemandEvents:

    def test_no_events_before_day_5(self, engine):
        """ST15-A: No demand events before day 5."""
        forecast = engine.forecast_demand(current_day=0, remaining_turns=720)
        day5_events = [e for e in forecast.upcoming_events if e["day"] <= 4]
        assert len(day5_events) == 0

    def test_town_event_at_day_10(self, engine):
        """ST15-B: Day 10 town demand event appears in forecast."""
        forecast = engine.forecast_demand(current_day=0, remaining_turns=720)
        day10 = [e for e in forecast.upcoming_events if e["day"] == 10 and e["source"] == "town"]
        assert len(day10) > 0

    def test_shop_event_present(self, engine):
        """ST15-C: Shop events appear in forecast."""
        forecast = engine.forecast_demand(current_day=0, remaining_turns=720)
        shop_events = [e for e in forecast.upcoming_events if e["source"] == "shop"]
        assert len(shop_events) > 0

    def test_events_outside_horizon_excluded(self, engine):
        """Events after remaining horizon are excluded."""
        # Only 2 turns remaining → no day-10 events
        forecast = engine.forecast_demand(current_day=29, remaining_turns=2)
        assert len(forecast.upcoming_events) == 0

    def test_total_expected_demand_aggregated(self, engine):
        """Total demand per product is the sum of all future events."""
        forecast = engine.forecast_demand(current_day=0, remaining_turns=720)
        assert "WHEAT" in forecast.total_expected_demand
        assert forecast.total_expected_demand["WHEAT"] > 0
