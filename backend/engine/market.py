"""
engine/market.py — MarketEngine (FR-013, FR-014).

Marginal unit pricing, demand events, sell planning.

Rules enforced:
- BR-005: Multi-unit sales use configured marginal price curve.
- BR-006: Capacity emergency overrides price optimisation.
- PRICE_FLOOR: No product sells below $1.
- MAX_ORDERS: Max 10 sell orders per turn.
- FR-014: Town/shop demand events fire on configured days,
  consuming market inventory and resetting price decay.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dataclasses import dataclass, field
from models.task import Task
import config as cfg


@dataclass
class MarketPlan:
    sell_actions: list[dict] = field(default_factory=list)
    total_proceeds: float = 0.0
    units_sold: int = 0
    order_count: int = 0
    reason: str = ""

    def to_dict(self) -> dict:
        return self.__dict__


@dataclass
class DemandForecast:
    upcoming_events: list[dict] = field(default_factory=list)
    total_expected_demand: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return self.__dict__


class MarketEngine:
    """
    Calculates marginal sale proceeds and generates sell tasks.
    """

    def __init__(self) -> None:
        self._sold_this_turn: dict[str, int] = {}
        self._order_count: int = 0
        # Accumulated cumulative units sold per product across all turns.
        # Town/shop demand events consume from this pool, resetting decay.
        self._market_inventory: dict[str, int] = {}
        self._fired_demand_days: set[int] = set()  # prevent double-firing

    def reset_turn(self) -> None:
        """Must be called at the start of each turn."""
        self._sold_this_turn = {}
        self._order_count = 0

    # ── pricing ───────────────────────────────────────────────────────────────

    def marginal_price(self, product: str, unit_index: int,
                       base_price: float) -> float:
        """
        FR-013: Price of the (unit_index)th unit sold this turn.
        price = max(PRICE_FLOOR, base_price - DECAY * unit_index)
        """
        price = base_price - cfg.MARKET_DECAY_PER_UNIT * unit_index
        return max(cfg.PRICE_FLOOR, price)

    def calculate_proceeds(self, product: str, units: int,
                           base_price: float) -> float:
        """
        Total proceeds for selling `units` of a product with marginal pricing.
        Uses cumulative market_inventory so decay persists across turns,
        but demand events reset it for a burst of profitable sales.
        """
        already_sold = self._market_inventory.get(product, 0)
        total = 0.0
        for i in range(units):
            total += self.marginal_price(product, already_sold + i, base_price)
        # Update market inventory for cross-turn decay tracking
        self._market_inventory[product] = already_sold + units
        # Also track within-turn for this call
        self._sold_this_turn[product] = (
            self._sold_this_turn.get(product, 0) + units
        )
        return round(total, 2)

    # ── sell planning ─────────────────────────────────────────────────────────

    def plan_sales(
        self,
        inventory: dict[str, int],
        market_prices: dict[str, float],
        warehouse_emergency: bool = False,
        is_endgame: bool = False,
    ) -> MarketPlan:
        """
        Generate a MarketPlan with up to MAX_ORDERS sell actions.

        Prioritises:
        1. Emergency relief (BR-006)
        2. Endgame liquidation
        3. Normal profitable sales
        """
        plan = MarketPlan()
        orders_remaining = cfg.MAX_ORDERS
        task_counter = 0

        for product, units in inventory.items():
            if units <= 0 or orders_remaining <= 0:
                break
            if product.endswith("_SEED") or product == "FERTILIZER" or product == "FEED":
                continue  # seeds/fertilizer cannot be sold

            base_price = market_prices.get(product, cfg.PRICE_FLOOR)
            sell_units = min(units, orders_remaining)
            proceeds = self.calculate_proceeds(product, sell_units, base_price)

            if proceeds > 0 or warehouse_emergency or is_endgame:
                plan.sell_actions.append({
                    "kind": "SELL",
                    "product": product,
                    "units": sell_units,
                    "expected_proceeds": proceeds,
                    "priority": cfg.PRIORITY_SELL,
                })
                plan.total_proceeds += proceeds
                plan.units_sold += sell_units
                plan.order_count += 1
                orders_remaining -= 1
                self._sold_this_turn[product] = (
                    self._sold_this_turn.get(product, 0) + sell_units
                )

        plan.reason = (
            "EMERGENCY" if warehouse_emergency
            else "ENDGAME" if is_endgame
            else "NORMAL"
        )
        return plan

    def record_sale(self, product: str, units: int) -> None:
        """Record a completed sale for this turn's tracking."""
        self._sold_this_turn[product] = self._sold_this_turn.get(product, 0) + units
        self._order_count += 1

    # ── demand event processing ───────────────────────────────────────────────

    def process_demand_events(self, current_day: int) -> list[dict]:
        """
        FR-014: Fire all demand events matching the current day.

        When a town or shop demand event fires, it "consumes" units from the
        market inventory pool. This resets the effective accumulated inventory
        for that product, so the next seller benefits from full (or boosted)
        base prices — simulating a real market surge.

        Returns a list of fired event dicts for telemetry/logging.
        """
        if current_day in self._fired_demand_days:
            return []  # already processed this day

        fired = []
        for event in cfg.DEMAND_EVENTS:
            if event["day"] == current_day:
                product = event["product"]
                consumed = event["units"]
                # Reduce accumulated market inventory by the consumed units.
                # If more is consumed than accumulated, floor at 0 (net positive demand).
                current_inv = self._market_inventory.get(product, 0)
                self._market_inventory[product] = max(0, current_inv - consumed)
                fired.append({
                    "day": current_day,
                    "product": product,
                    "units_consumed": consumed,
                    "source": event["source"],
                    "market_inventory_after": self._market_inventory[product],
                })
        if fired:
            self._fired_demand_days.add(current_day)
        return fired

    # ── demand forecast ───────────────────────────────────────────────────────

    def forecast_demand(self, current_day: int, remaining_turns: int) -> DemandForecast:
        """
        FR-014: Identify upcoming demand events within the remaining horizon.
        """
        turns_remaining = remaining_turns
        days_remaining = turns_remaining // cfg.TURNS_PER_DAY
        upcoming = []
        total: dict[str, int] = {}

        for event in cfg.DEMAND_EVENTS:
            if event["day"] > current_day and event["day"] <= current_day + days_remaining:
                upcoming.append({
                    "day": event["day"],
                    "product": event["product"],
                    "units": event["units"],
                    "source": event["source"],
                    "turns_until": (event["day"] - current_day) * cfg.TURNS_PER_DAY,
                })
                total[event["product"]] = total.get(event["product"], 0) + event["units"]

        return DemandForecast(
            upcoming_events=sorted(upcoming, key=lambda e: e["day"]),
            total_expected_demand=total,
        )
