"""
engine/warehouse.py — WarehouseManager (FR-012).

Tracks shed + carried inventory, forecasts overflow, triggers emergency sales.

Rules enforced:
- Seeds do NOT count toward the 100-unit shed capacity.
- Carried goods DO count toward total physical inventory.
- BR-006: Physical capacity risk overrides waiting for a better price.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dataclasses import dataclass, field
import config as cfg


@dataclass
class WarehouseForecast:
    current_total: int
    capacity: int
    utilization_pct: float
    projected_inflow: int          # expected harvest units this turn
    projected_outflow: int         # expected sales this turn
    projected_total: int
    overflow_risk: bool            # True when projected_total >= capacity
    emergency_relief_needed: bool  # True when utilization >= 85%
    relief_units_needed: int       # units to sell to drop below 85%

    def to_dict(self) -> dict:
        return self.__dict__


class WarehouseManager:
    """
    Manages the shared shed inventory and per-worker carried inventory.
    """

    def __init__(self) -> None:
        self._shed: dict[str, int] = {}          # {product: units}  (seeds excluded)
        self._carried: dict[int, dict[str, int]] = {}  # {worker_id: {product: units}}
        self._seeds: dict[str, int] = {}         # seeds stored separately

    # ── inventory operations ──────────────────────────────────────────────────

    def add_to_shed(self, product: str, units: int) -> bool:
        """
        Add units to shed. Returns False if it would exceed capacity.
        Seeds bypass the capacity check.
        """
        if product.endswith("_SEED") or product == "FERTILIZER" or product == "FEED":
            self._seeds[product] = self._seeds.get(product, 0) + units
            return True

        if self.total_non_seed_units() + units > cfg.SHED_CAPACITY:
            return False
        self._shed[product] = self._shed.get(product, 0) + units
        return True

    def remove_from_shed(self, product: str, units: int) -> bool:
        """Remove units (e.g. after a SELL). Returns False if insufficient."""
        available = self._shed.get(product, 0)
        if available < units:
            return False
        self._shed[product] = available - units
        return True

    def get_shed(self, product: str) -> int:
        return self._shed.get(product, 0)

    def get_seeds(self, product: str) -> int:
        return self._seeds.get(product, 0)

    def remove_seed(self, product: str, units: int = 1) -> bool:
        available = self._seeds.get(product, 0)
        if available < units:
            return False
        self._seeds[product] = available - units
        return True

    def add_to_worker(self, worker_id: int, product: str, units: int) -> bool:
        """Add units to a worker's carried inventory."""
        worker_inv = self._carried.setdefault(worker_id, {})
        current = sum(worker_inv.values())
        if current + units > cfg.WORKER_CAPACITY:
            return False
        worker_inv[product] = worker_inv.get(product, 0) + units
        return True

    def remove_from_worker(self, worker_id: int, product: str, units: int) -> bool:
        worker_inv = self._carried.get(worker_id, {})
        if worker_inv.get(product, 0) < units:
            return False
        worker_inv[product] -= units
        return True

    def transfer_worker_to_shed(self, worker_id: int) -> dict[str, int]:
        """Move all worker-carried goods to the shed (e.g. after harvest)."""
        worker_inv = self._carried.get(worker_id, {})
        transferred = {}
        for product, units in list(worker_inv.items()):
            if units > 0 and self.add_to_shed(product, units):
                transferred[product] = units
                worker_inv[product] = 0
        return transferred

    # ── forecasting ───────────────────────────────────────────────────────────

    def forecast(self, projected_inflow: int = 0,
                 projected_outflow: int = 0) -> WarehouseForecast:
        """
        FR-012: Forecast capacity and flag emergency relief if needed.

        Thresholds:
        - 85%: generate relief sale/drop task
        - 90%: urgent
        - 100%: emergency
        """
        current = self.total_non_seed_units()
        projected = max(0, current + projected_inflow - projected_outflow)
        util = current / cfg.SHED_CAPACITY if cfg.SHED_CAPACITY > 0 else 0.0
        overflow = projected >= cfg.SHED_CAPACITY
        emergency = util >= 0.85
        target_units = int(cfg.SHED_CAPACITY * 0.80)
        relief_needed = max(0, current - target_units) if emergency else 0

        return WarehouseForecast(
            current_total=current,
            capacity=cfg.SHED_CAPACITY,
            utilization_pct=round(util * 100, 1),
            projected_inflow=projected_inflow,
            projected_outflow=projected_outflow,
            projected_total=projected,
            overflow_risk=overflow,
            emergency_relief_needed=emergency,
            relief_units_needed=relief_needed,
        )

    # ── aggregates ────────────────────────────────────────────────────────────

    def total_non_seed_units(self) -> int:
        """Total units counting shed + all carried worker goods (seeds excluded)."""
        shed_total = sum(self._shed.values())
        carried_total = sum(
            sum(inv.values()) for inv in self._carried.values()
        )
        return shed_total + carried_total

    def shed_snapshot(self) -> dict:
        return {**self._shed}

    def all_inventory(self) -> dict[str, int]:
        """Merged view: shed + carried per product."""
        result: dict[str, int] = {}
        for product, units in self._shed.items():
            result[product] = result.get(product, 0) + units
        for worker_inv in self._carried.values():
            for product, units in worker_inv.items():
                result[product] = result.get(product, 0) + units
        return result
