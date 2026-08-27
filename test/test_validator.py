"""
test/test_validator.py — FR-018: Sequential action validation.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from engine.validator import ActionValidator
import config as cfg


@pytest.fixture
def validator():
    return ActionValidator()


def base_state(cash=500.0, shed=None, seeds=None, fertilizer=3, feed=5, farms=None, structures=None):
    if shed is None:
        shed = {"WHEAT": 10}
    if seeds is None:
        seeds = {"WHEAT_SEED": 5, "TOMATO_SEED": 2}
    if farms is None:
        farms = [
            {"row": 0, "col": 0, "status": "EMPTY",  "locked": False},
            {"row": 0, "col": 1, "status": "GROWING", "locked": False},
            {"row": 0, "col": 2, "status": "MATURE",  "locked": False},
            {"row": 0, "col": 3, "status": "LOCKED",  "locked": True},
        ]
    return {
        "cash": cash,
        "shed_inventory": shed,
        "seeds": seeds,
        "fertilizer": fertilizer,
        "feed": feed,
        "market_orders_used": 0,
        "structures": structures or ["BARN"],
        "farms": farms,
    }


class TestIllegalActions:

    def test_valid_sell_accepted(self, validator):
        """ST19-A: SELL with sufficient inventory → accepted."""
        result = validator.validate_all(
            [{"kind": "SELL", "product": "WHEAT", "units": 5}],
            base_state(),
        )
        assert len(result.accepted) == 1

    def test_sell_insufficient_inventory_rejected(self, validator):
        """Selling more than available → rejected."""
        result = validator.validate_all(
            [{"kind": "SELL", "product": "WHEAT", "units": 100}],
            base_state(shed={"WHEAT": 5}),
        )
        assert len(result.rejected) == 1

    def test_sell_seed_rejected(self, validator):
        """Cannot sell seeds."""
        result = validator.validate_all(
            [{"kind": "SELL", "product": "WHEAT_SEED", "units": 1}],
            base_state(),
        )
        assert len(result.rejected) == 1

    def test_max_orders_limit(self, validator):
        """ST18-E: More than MAX_ORDERS sell actions in one turn → extras rejected."""
        actions = [
            {"kind": "SELL", "product": "WHEAT", "units": 1}
            for _ in range(cfg.MAX_ORDERS + 3)
        ]
        state = base_state(shed={"WHEAT": 100})
        result = validator.validate_all(actions, state)
        # Only first MAX_ORDERS should be accepted
        assert len(result.accepted) <= cfg.MAX_ORDERS

    def test_harvest_requires_mature_crop(self, validator):
        """HARVEST on a non-mature tile → rejected."""
        result = validator.validate_all(
            [{"kind": "HARVEST", "target": [0, 1]}],  # GROWING, not MATURE
            base_state(),
        )
        assert len(result.rejected) == 1

    def test_harvest_mature_accepted(self, validator):
        result = validator.validate_all(
            [{"kind": "HARVEST", "target": [0, 2]}],  # MATURE
            base_state(),
        )
        assert len(result.accepted) == 1

    def test_plant_on_locked_tile_rejected(self, validator):
        """ST19-D: Planting on LOCKED tile → rejected."""
        result = validator.validate_all(
            [{"kind": "PLANT", "crop": "WHEAT", "target": [0, 3]}],
            base_state(),
        )
        assert len(result.rejected) == 1

    def test_fertilize_without_fertilizer_rejected(self, validator):
        """Missing fertilizer → rejected."""
        result = validator.validate_all(
            [{"kind": "FERTILIZE", "target": [0, 1]}],
            base_state(fertilizer=0),
        )
        assert len(result.rejected) == 1

    def test_sequential_validation_state_update(self, validator):
        """BR-012: Worker 1 uses last WHEAT → Worker 2 sees 0 WHEAT."""
        actions = [
            {"kind": "SELL", "product": "WHEAT", "units": 5},  # uses all 5
            {"kind": "SELL", "product": "WHEAT", "units": 1},  # should fail
        ]
        state = base_state(shed={"WHEAT": 5})
        result = validator.validate_all(actions, state)
        assert len(result.accepted) == 1
        assert len(result.rejected) == 1

    def test_feed_without_feed_supply_rejected(self, validator):
        result = validator.validate_all(
            [{"kind": "FEED", "animal_id": "cow_0"}],
            base_state(feed=0),
        )
        assert len(result.rejected) == 1

    def test_buy_animal_without_structure_rejected(self, validator):
        result = validator.validate_all(
            [{"kind": "BUY_ANIMAL", "kind_animal": "CHICKEN"}],
            base_state(structures=[]),  # No COOP
        )
        assert len(result.rejected) == 1
