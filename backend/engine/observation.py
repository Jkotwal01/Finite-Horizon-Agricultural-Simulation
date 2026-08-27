"""
engine/observation.py — ObservationAdapter (FR-001).

Converts raw game observation dicts into a CanonicalState.
Does NOT make strategy decisions. Does NOT invent missing fields.
"""
from __future__ import annotations
from typing import Any

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.state import CanonicalState
import config as cfg


class ObservationAdapter:
    """
    Reads raw environment observation and normalises it to CanonicalState.

    Verification (FR-001):
    ✓ Required keys exist
    ✓ Types are normalised (int/float coercions)
    ✓ Malformed input is rejected with ValueError
    """

    REQUIRED_TOP_LEVEL = {"turn", "cash", "farms", "market"}

    def normalise(self, raw: dict[str, Any]) -> CanonicalState:
        """
        Convert a raw observation dict to CanonicalState.

        Raises ValueError if required keys are missing.
        """
        missing = self.REQUIRED_TOP_LEVEL - set(raw.keys())
        if missing:
            raise ValueError(f"Observation missing required keys: {missing}")

        turn = int(raw["turn"])
        day = turn // cfg.TURNS_PER_DAY
        hour = turn % cfg.TURNS_PER_DAY

        return CanonicalState(
            turn=turn,
            day=day,
            hour=hour,
            cash=float(raw.get("cash", 0.0)),
            farms=self._normalise_farms(raw.get("farms", [])),
            market=self._normalise_market(raw.get("market", {})),
            shops=raw.get("shops", []),
            town=raw.get("town", {}),
            rules=self._build_rules_snapshot(),
            workers=raw.get("workers", []),
            structures=raw.get("structures", []),
            shed_inventory=raw.get("shed_inventory", {}),
            animals=raw.get("animals", []),
        )

    # ── private helpers ───────────────────────────────────────────────────────

    def _normalise_farms(self, farms: list) -> list[dict]:
        """Ensure each tile has row, col, status fields."""
        normalised = []
        for tile in farms:
            normalised.append({
                "row": int(tile.get("row", 0)),
                "col": int(tile.get("col", 0)),
                "status": str(tile.get("status", "EMPTY")),
                "crop": tile.get("crop"),
                "locked": bool(tile.get("locked", False)),
            })
        return normalised

    def _normalise_market(self, market: dict) -> dict:
        """Ensure each product entry has price and inventory fields."""
        normalised = {}
        for product, info in market.items():
            if isinstance(info, dict):
                normalised[str(product)] = {
                    "price": float(info.get("price", 1.0)),
                    "inventory": int(info.get("inventory", 0)),
                    "sold_this_turn": int(info.get("sold_this_turn", 0)),
                }
            else:
                normalised[str(product)] = {
                    "price": float(info),
                    "inventory": 0,
                    "sold_this_turn": 0,
                }
        return normalised

    def _build_rules_snapshot(self) -> dict:
        """Return a snapshot of current config for this turn."""
        return {
            "total_turns": cfg.TOTAL_TURNS,
            "turns_per_day": cfg.TURNS_PER_DAY,
            "max_orders": cfg.MAX_ORDERS,
            "shed_capacity": cfg.SHED_CAPACITY,
            "worker_capacity": cfg.WORKER_CAPACITY,
            "price_floor": cfg.PRICE_FLOOR,
        }
