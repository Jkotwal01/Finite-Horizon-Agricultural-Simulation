"""
test/test_crops.py — FR-005, FR-006, FR-007: Crop lifecycle, watering, fertilizer.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from engine.crop_manager import CropManager
import config as cfg


@pytest.fixture
def mgr():
    return CropManager()


class TestCropEvents:

    def test_planting_creates_state(self, mgr):
        """ST06-A: Plant a crop → CropState exists on that tile."""
        crop = mgr.plant("WHEAT", 0, 0, current_turn=0)
        assert crop.crop == "WHEAT"
        assert crop.planted_turn == 0
        assert crop.age == 0

    def test_duplicate_plant_raises(self, mgr):
        """ST06-C: Cannot plant on an occupied tile."""
        mgr.plant("WHEAT", 0, 0, 0)
        with pytest.raises(ValueError):
            mgr.plant("TOMATO", 0, 0, 0)

    def test_unknown_crop_raises(self, mgr):
        with pytest.raises(ValueError):
            mgr.plant("DRAGON_FRUIT", 0, 0, 0)

    def test_crop_matures_at_correct_turn(self, mgr):
        """WHEAT matures in 48 turns."""
        mgr.plant("WHEAT", 0, 0, current_turn=0)
        # Water each turn to keep alive
        for t in range(1, 49):
            mgr.water_crop(0, 0)
            events = mgr.advance_turn(t)
            if t == 48:
                matured = [e for e in events if e["type"] == "MATURED"]
                assert len(matured) == 1

    def test_ongoing_crop_produces_repeatedly(self, mgr):
        """TOMATO is ongoing — must produce more than once (no cap)."""
        mgr.plant("TOMATO", 0, 0, current_turn=0)
        productions = 0
        for t in range(1, 200):
            mgr.water_crop(0, 0)
            events = mgr.advance_turn(t)
            productions += sum(1 for e in events if e["type"] == "PRODUCED")
        # Should produce multiple times (no artificial cap)
        assert productions >= 3


class TestDailyWater:

    def test_water_task_generated(self, mgr):
        """ST07-A: Newly planted crop → water task generated."""
        mgr.plant("WHEAT", 0, 0, current_turn=0)
        # Simulate one advance (sets water_status to PENDING)
        mgr.advance_turn(1)
        tasks = mgr.generate_water_tasks(1)
        assert len(tasks) == 1
        assert tasks[0].kind == "WATER"
        assert tasks[0].priority == cfg.PRIORITY_SURVIVAL

    def test_watering_resets_missed_counter(self, mgr):
        """After watering, consecutive_missed_water resets to 0."""
        mgr.plant("WHEAT", 0, 0, 0)
        # Water BEFORE advancing turn 1 so it's not counted as a miss
        mgr.water_crop(0, 0)
        mgr.advance_turn(1)   # watered → counter stays 0
        crop = mgr.get_all_crops()[0]
        assert crop.consecutive_missed_water == 0
        # Now miss turn 2 (no water) → counter = 1
        mgr.advance_turn(2)
        assert crop.consecutive_missed_water == 1
        # Water and advance turn 3 → counter resets
        mgr.water_crop(0, 0)
        mgr.advance_turn(3)
        assert crop.consecutive_missed_water == 0


    def test_two_missed_turns_kills_crop(self, mgr):
        """Missing 2 consecutive waterings kills the crop."""
        mgr.plant("WHEAT", 0, 0, 0)
        events_all = []
        for t in range(1, 4):  # no watering at all
            events_all.extend(mgr.advance_turn(t))
        dead = [e for e in events_all if e["type"] == "DEAD"]
        assert len(dead) == 1

    def test_multiple_crops_multiple_tasks(self, mgr):
        """Multiple crops each generate their own water task."""
        mgr.plant("WHEAT", 0, 0, 0)
        mgr.plant("TOMATO", 0, 1, 0)
        mgr.advance_turn(1)
        tasks = mgr.generate_water_tasks(1)
        assert len(tasks) == 2


class TestFertilizerWindow:

    def test_fertilize_eligible_crop(self, mgr):
        """ST08-A: Crop within window can be fertilized → yield bonus applied."""
        mgr.plant("WHEAT", 0, 0, 0)
        # Age is 0, window is (0, 24) — eligible
        result = mgr.fertilize_crop(0, 0, current_turn=1)
        assert result is True
        crop = mgr.get_all_crops()[0]
        assert crop.fertilized is True
        assert crop.yield_units > crop.base_yield

    def test_fertilize_outside_window(self, mgr):
        """ST08-B: Crop too old (age > 24 for WHEAT) → not fertilized."""
        mgr.plant("WHEAT", 0, 0, 0)
        # Age the crop past the window
        for t in range(1, 30):
            mgr.water_crop(0, 0)
            mgr.advance_turn(t)
        result = mgr.fertilize_crop(0, 0, current_turn=30)
        assert result is False

    def test_no_double_fertilize(self, mgr):
        """Fertilizing twice returns False on second attempt."""
        mgr.plant("TOMATO", 1, 1, 0)
        mgr.fertilize_crop(1, 1, 1)
        result = mgr.fertilize_crop(1, 1, 2)
        assert result is False

    def test_zero_fertilizer_no_tasks(self, mgr):
        """ST08-C: No fertilizer available → no tasks generated."""
        mgr.plant("WHEAT", 0, 0, 0)
        tasks = mgr.generate_fertilizer_tasks(fertilizer_available=0)
        assert tasks == []

    def test_one_unit_multiple_crops(self, mgr):
        """1 unit of fertilizer → only 1 task despite 2 eligible crops."""
        mgr.plant("WHEAT", 0, 0, 0)
        mgr.plant("WHEAT", 0, 1, 0)
        tasks = mgr.generate_fertilizer_tasks(fertilizer_available=1)
        assert len(tasks) == 1

    def test_viability_check(self, mgr):
        """BR-011: Crop that cannot mature before horizon is not viable."""
        # 48 turns to mature, but only 10 turns left
        viable = mgr.can_mature_before("WHEAT", current_turn=710, horizon=720)
        assert not viable
        viable = mgr.can_mature_before("WHEAT", current_turn=600, horizon=720)
        assert viable
