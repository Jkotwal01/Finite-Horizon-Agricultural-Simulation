"""
test_demand_integration.py — FR-014 Demand Event Integration Tests

Verifies:
- Demand events fire on the correct day.
- Town/shop consumption reduces accumulated market inventory.
- Events fire only once per day.
- Selling after a demand event yields higher proceeds (price decay reset).
- Events outside remaining horizon are excluded from forecasts.
"""
from backend.engine.market import MarketEngine
import backend.config as cfg


class TestDemandEventProcessing:

    def setup_method(self):
        self.market = MarketEngine()

    def test_no_events_fire_before_day_5(self):
        """Day 0 → 4 should fire no events."""
        for day in range(5):
            fired = self.market.process_demand_events(day)
            assert fired == [], f"Unexpected events on day {day}: {fired}"

    def test_shop_event_fires_on_day_5(self):
        """MILK demand event should fire on Day 5."""
        fired = self.market.process_demand_events(5)
        products = [e["product"] for e in fired]
        assert "MILK" in products

    def test_town_event_fires_on_day_10_wheat(self):
        """WHEAT town demand event fires on Day 10."""
        fired = self.market.process_demand_events(10)
        products = [e["product"] for e in fired]
        assert "WHEAT" in products

    def test_town_event_fires_on_day_10_tomato(self):
        """TOMATO town demand event fires on Day 10."""
        fired = self.market.process_demand_events(10)
        products = [e["product"] for e in fired]
        assert "TOMATO" in products

    def test_events_fire_only_once_per_day(self):
        """Calling process_demand_events for the same day twice should not double-fire."""
        first = self.market.process_demand_events(10)
        second = self.market.process_demand_events(10)
        assert len(first) > 0, "Should fire on first call"
        assert second == [], "Should not fire again on same day"

    def test_demand_event_resets_market_inventory(self):
        """
        Selling many units of WHEAT before Day 10 should accumulate decay.
        After the Day 10 demand event consumes 10 units from market inventory,
        the next sale should yield higher proceeds (less accumulated decay).
        """
        base_price = cfg.CROP_RULES["WHEAT"]["base_sell_price"]  # $8.0

        # Sell 15 WHEAT — market_inventory["WHEAT"] = 15 (heavy decay)
        proceeds_heavy = self.market.calculate_proceeds("WHEAT", 15, base_price)

        # Now fire Day 10 demand event (WHEAT town: 10 units consumed)
        fired = self.market.process_demand_events(10)
        wheat_events = [e for e in fired if e["product"] == "WHEAT"]
        assert len(wheat_events) == 1

        # market_inventory should be reduced from 15 → 5 (15 - 10 = 5)
        assert wheat_events[0]["market_inventory_after"] == 5

        # Next sale of 5 WHEAT units starts at decay-index 5, not 15
        self.market.reset_turn()
        proceeds_post_event = self.market.calculate_proceeds("WHEAT", 5, base_price)

        # Compare vs selling 5 more without reset (starts at decay-index 15)
        fresh_market = MarketEngine()
        # Simulate the "no event" world: already sold 15
        fresh_market.calculate_proceeds("WHEAT", 15, base_price)
        fresh_market.reset_turn()
        proceeds_no_reset = fresh_market.calculate_proceeds("WHEAT", 5, base_price)

        assert proceeds_post_event > proceeds_no_reset, (
            f"Post-demand proceeds ({proceeds_post_event}) should exceed "
            f"no-reset proceeds ({proceeds_no_reset})"
        )

    def test_demand_consumption_floors_at_zero(self):
        """
        If demand exceeds what was sold (market_inventory < consumed), floor at 0.
        """
        # No sales yet → market_inventory["WHEAT"] = 0
        fired = self.market.process_demand_events(10)
        wheat = next(e for e in fired if e["product"] == "WHEAT")
        assert wheat["market_inventory_after"] == 0  # can't go negative

    def test_multiple_events_same_day(self):
        """Day 10 should fire both WHEAT and TOMATO town events."""
        fired = self.market.process_demand_events(10)
        products = {e["product"] for e in fired}
        assert "WHEAT" in products
        assert "TOMATO" in products

    def test_event_source_recorded(self):
        """Each fired event should carry its source (town/shop)."""
        fired = self.market.process_demand_events(10)
        for event in fired:
            assert "source" in event
            assert event["source"] in ("town", "shop")

    def test_forecast_excludes_past_events(self):
        """
        forecast_demand should not include events before the current day.
        """
        forecast = self.market.forecast_demand(current_day=11, remaining_turns=720)
        for event in forecast.upcoming_events:
            assert event["day"] > 11, f"Event on day {event['day']} is in the past!"

    def test_forecast_excludes_out_of_horizon_events(self):
        """
        Events too far in the future (beyond remaining turns) must be excluded.
        """
        # Start at day 0, only 48 turns left (~2 days)
        forecast = self.market.forecast_demand(current_day=0, remaining_turns=48)
        for event in forecast.upcoming_events:
            assert event["day"] <= 2, (
                f"Event on day {event['day']} is beyond 2-day horizon"
            )

    def test_total_expected_demand_aggregated(self):
        """
        forecast_demand.total_expected_demand should sum all matching event units
        across multiple events for the same product.
        """
        # WHEAT has events on day 10 (10 units) and day 20 (15 units)
        forecast = self.market.forecast_demand(current_day=0, remaining_turns=720)
        wheat_demand = forecast.total_expected_demand.get("WHEAT", 0)
        assert wheat_demand >= 25, f"Expected at least 25 WHEAT demand, got {wheat_demand}"
