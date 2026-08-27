"""
test/test_endgame.py — FR-020: Endgame mode and terminal result tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from engine.endgame import EndgameManager
from models.crop import CropState
import config as cfg


@pytest.fixture
def mgr():
    return EndgameManager()


def make_mature_crop(crop_type="WHEAT", row=0, col=0, age=50):
    rules = cfg.CROP_RULES[crop_type]
    c = CropState(
        crop=crop_type, tile_row=row, tile_col=col,
        planted_turn=0, age=age,
        yield_units=rules["yield_units"],
        base_yield=rules["yield_units"],
        next_production_turn=48,
        is_mature=True,
    )
    return c


def make_unmatured_crop(crop_type="WHEAT", age=10):
    rules = cfg.CROP_RULES[crop_type]
    c = CropState(
        crop=crop_type, tile_row=1, tile_col=0,
        planted_turn=710, age=age,
        yield_units=rules["yield_units"],
        base_yield=rules["yield_units"],
        next_production_turn=710 + rules["maturity_turns"],
        is_mature=False,
    )
    return c


class TestEndgame:

    def test_early_endgame_viable_crops(self, mgr):
        """ST21-A: Mature crop within horizon → viable."""
        crop = make_mature_crop()
        plan = mgr.build_plan(
            crops=[crop], inventory={},
            market_prices={"WHEAT": 8.0},
            current_turn=670, remaining_turns=50, cash=100.0,
        )
        assert len(plan.viable_crops) == 1

    def test_non_viable_crop_excluded(self, mgr):
        """ST21-B: Crop cannot mature before Turn 720 → non-viable."""
        crop = make_unmatured_crop("WHEAT", age=5)
        plan = mgr.build_plan(
            crops=[crop], inventory={},
            market_prices={"WHEAT": 8.0},
            current_turn=710, remaining_turns=10, cash=100.0,
        )
        assert len(plan.non_viable_crops) == 1
        assert len(plan.viable_crops) == 0

    def test_harvest_actions_for_mature_crops(self, mgr):
        """Mature viable crops get harvest actions."""
        crop = make_mature_crop()
        plan = mgr.build_plan(
            crops=[crop], inventory={},
            market_prices={"WHEAT": 8.0},
            current_turn=670, remaining_turns=50, cash=100.0,
        )
        assert len(plan.harvest_actions) == 1
        assert plan.harvest_actions[0]["kind"] == "HARVEST"

    def test_sell_all_inventory(self, mgr):
        """ST21-C: All sellable inventory generates sell actions."""
        plan = mgr.build_plan(
            crops=[], inventory={"WHEAT": 10, "TOMATO": 5},
            market_prices={"WHEAT": 8.0, "TOMATO": 10.0},
            current_turn=715, remaining_turns=5, cash=100.0,
        )
        assert len(plan.sell_actions) >= 1
        products_sold = [a["product"] for a in plan.sell_actions]
        assert "WHEAT" in products_sold or "TOMATO" in products_sold

    def test_seeds_not_in_sell_plan(self, mgr):
        """Seeds cannot be sold."""
        plan = mgr.build_plan(
            crops=[], inventory={"WHEAT_SEED": 5, "FERTILIZER": 3},
            market_prices={},
            current_turn=715, remaining_turns=5, cash=100.0,
        )
        for action in plan.sell_actions:
            assert not action["product"].endswith("_SEED")
            assert action["product"] != "FERTILIZER"

    def test_is_final_turn_flag(self, mgr):
        """is_final_turn=True when remaining_turns <= 1."""
        plan = mgr.build_plan(
            crops=[], inventory={}, market_prices={},
            current_turn=719, remaining_turns=1, cash=0.0,
        )
        assert plan.is_final_turn is True

    def test_should_not_plant_non_viable(self, mgr):
        """BR-011: should_plant returns False when crop can't mature."""
        result = mgr.should_plant("WHEAT", current_turn=710, remaining_turns=5)
        assert result is False

    def test_should_plant_viable(self, mgr):
        result = mgr.should_plant("WHEAT", current_turn=600, remaining_turns=120)
        assert result is True
