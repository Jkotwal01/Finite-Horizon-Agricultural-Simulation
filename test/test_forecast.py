"""
test/test_forecast.py — FR-015: Production forecast tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from engine.forecast import ForecastEngine
from models.crop import CropState
from models.animal import AnimalState
import config as cfg


@pytest.fixture
def engine():
    return ForecastEngine()


def make_crop(crop_type, planted_turn=0, age=0, is_mature=False, harvest_count=0):
    rules = cfg.CROP_RULES[crop_type]
    c = CropState(
        crop=crop_type,
        tile_row=0, tile_col=0,
        planted_turn=planted_turn,
        age=age,
        yield_units=rules["yield_units"],
        base_yield=rules["yield_units"],
        next_production_turn=planted_turn + rules["maturity_turns"],
        is_mature=is_mature,
    )
    if is_mature:
        c.next_production_turn = planted_turn + rules["maturity_turns"]
    return c


class TestProductionSchedule:

    def test_one_time_crop_single_event(self, engine):
        """ST16-A: WHEAT (one-time) → exactly one production event."""
        crop = make_crop("WHEAT", planted_turn=0)
        events = engine.forecast_crops([crop], current_turn=0, horizon=720)
        assert len(events) == 1
        assert events[0]["crop"] == "WHEAT"

    def test_ongoing_crop_multiple_events(self, engine):
        """ST16-B: TOMATO (ongoing) → multiple events, no cap."""
        crop = make_crop("TOMATO", planted_turn=0)
        events = engine.forecast_crops([crop], current_turn=0, horizon=720)
        # Should produce at turn 72, 96, 120, ... → many events
        assert len(events) >= 3

    def test_events_bounded_by_horizon(self, engine):
        """All events have turn <= horizon."""
        crop = make_crop("TOMATO", planted_turn=0)
        horizon = 200
        events = engine.forecast_crops([crop], current_turn=0, horizon=horizon)
        for e in events:
            assert e["turn"] <= horizon

    def test_late_planting_excluded(self, engine):
        """ST16-D: Crop planted too late → harvest turn exceeds horizon → no event."""
        crop = make_crop("WHEAT", planted_turn=700)
        crop.next_production_turn = 700 + 48  # = 748 > 720
        events = engine.forecast_crops([crop], current_turn=700, horizon=720)
        assert len(events) == 0

    def test_animal_product_forecast(self, engine):
        """ST16-C: Placed animal → production events in forecast."""
        animal = AnimalState(
            animal_id="chicken_0",
            kind="CHICKEN",
            location="PLACED",
            tile_row=0, tile_col=0,
            is_alive=True,
            next_product_turn=12,
        )
        events = engine.forecast_animals([animal], current_turn=0, horizon=120)
        assert len(events) >= 1
        assert events[0]["product"] == "EGGS"

    def test_dead_crop_excluded(self, engine):
        """Dead crops produce no forecast events."""
        crop = make_crop("WHEAT", planted_turn=0)
        crop.is_dead = True
        events = engine.forecast_crops([crop], current_turn=0, horizon=720)
        assert len(events) == 0

    def test_total_value_computed(self, engine):
        """full_forecast returns aggregate total_value."""
        crop = make_crop("WHEAT", planted_turn=0)
        forecast = engine.full_forecast([crop], [], current_turn=0, horizon=720)
        assert forecast.total_value > 0
        assert "WHEAT" in forecast.total_by_product
