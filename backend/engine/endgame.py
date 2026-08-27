"""
engine/endgame.py — EndgameManager (FR-020).

Handles the final-horizon liquidation phase (Turn 670+).

Rules:
- BR-011: Stop planting crops that cannot mature before Turn 720.
- Harvest all viable crops.
- Sell all inventory according to endgame policy.
- Protect warehouse capacity in final turns.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.plan import EndgamePlan
from models.crop import CropState
import config as cfg


class EndgameManager:
    """
    Produces EndgamePlan when the simulation enters endgame mode.
    """

    def build_plan(
        self,
        crops: list[CropState],
        inventory: dict[str, int],
        market_prices: dict[str, float],
        current_turn: int,
        remaining_turns: int,
        cash: float,
    ) -> EndgamePlan:
        """
        FR-020: Classify crops as viable/non-viable, plan harvest and sale.
        """
        horizon = current_turn + remaining_turns
        viable = []
        non_viable = []

        for crop in crops:
            if crop.is_dead:
                continue
            rules = cfg.CROP_RULES[crop.crop]
            if rules["one_time"]:
                # Viable only if it can mature before the final turn
                turns_to_maturity = max(0, rules["maturity_turns"] - crop.age)
                if current_turn + turns_to_maturity <= horizon:
                    viable.append(crop.to_dict())
                else:
                    non_viable.append(crop.to_dict())
            else:
                # Ongoing: viable if at least one more harvest fits
                if crop.is_mature and crop.next_production_turn is not None:
                    if crop.next_production_turn <= horizon:
                        viable.append(crop.to_dict())
                    else:
                        non_viable.append(crop.to_dict())
                else:
                    turns_to_maturity = max(0, rules["maturity_turns"] - crop.age)
                    if current_turn + turns_to_maturity <= horizon:
                        viable.append(crop.to_dict())
                    else:
                        non_viable.append(crop.to_dict())

        # Harvest actions for mature viable crops
        harvest_actions = [
            {
                "kind": "HARVEST",
                "tile": [c["tile_row"], c["tile_col"]],
                "crop": c["crop"],
                "priority": cfg.PRIORITY_HARVEST,
            }
            for c in viable if c.get("is_mature")
        ]

        # Sell all sellable inventory
        sell_actions = []
        orders_used = 0
        total_proceeds = 0.0
        for product, units in inventory.items():
            if units <= 0 or orders_used >= cfg.MAX_ORDERS:
                break
            if product.endswith("_SEED") or product == "FERTILIZER" or product == "FEED":
                continue
            base_price = market_prices.get(product, cfg.PRICE_FLOOR)
            sell_units = min(units, cfg.MAX_ORDERS - orders_used)
            proceeds = sum(
                max(cfg.PRICE_FLOOR, base_price - cfg.MARKET_DECAY_PER_UNIT * i)
                for i in range(sell_units)
            )
            sell_actions.append({
                "kind": "SELL",
                "product": product,
                "units": sell_units,
                "expected_proceeds": round(proceeds, 2),
                "priority": cfg.PRIORITY_SELL,
            })
            total_proceeds += proceeds
            orders_used += 1

        return EndgamePlan(
            viable_crops=viable,
            non_viable_crops=non_viable,
            harvest_actions=harvest_actions,
            sell_actions=sell_actions,
            expected_final_cash=round(cash + total_proceeds, 2),
            is_final_turn=(remaining_turns <= 1),
        )

    def should_plant(self, crop_type: str, current_turn: int,
                     remaining_turns: int) -> bool:
        """BR-011: Return False if crop cannot complete one harvest before horizon."""
        if crop_type not in cfg.CROP_RULES:
            return False
        maturity = cfg.CROP_RULES[crop_type]["maturity_turns"]
        return (current_turn + maturity) < (current_turn + remaining_turns)
