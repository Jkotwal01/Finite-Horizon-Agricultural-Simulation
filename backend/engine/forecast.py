"""
engine/forecast.py — ForecastEngine (FR-015).

Generates dated future production events through the remaining horizon.

Rules:
- Uses remaining turns (BR-007 Finite horizon).
- Applies authoritative crop/animal production rules.
- Does NOT impose an artificial cap on ongoing crop production.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dataclasses import dataclass, field
from models.crop import CropState
from models.animal import AnimalState
import config as cfg


@dataclass
class ProductionForecast:
    crop_events: list[dict] = field(default_factory=list)
    animal_events: list[dict] = field(default_factory=list)
    total_by_product: dict[str, int] = field(default_factory=dict)
    total_value: float = 0.0

    def to_dict(self) -> dict:
        return {
            "crop_events": self.crop_events,
            "animal_events": self.animal_events,
            "total_by_product": self.total_by_product,
            "total_value": round(self.total_value, 2),
        }


class ForecastEngine:
    """
    Predicts all future production events within the remaining horizon.
    """

    def forecast_crops(
        self,
        crops: list[CropState],
        current_turn: int,
        horizon: int,
    ) -> list[dict]:
        """
        Generate dated production events for all active crops.
        Only includes events that can occur on or before the horizon.
        """
        events = []
        for crop in crops:
            if crop.is_dead:
                continue
            rules = cfg.CROP_RULES[crop.crop]

            if rules["one_time"]:
                # One-time crop: single harvest at maturity
                harvest_turn = crop.next_production_turn
                if harvest_turn is not None and harvest_turn <= horizon:
                    events.append({
                        "turn": harvest_turn,
                        "crop": crop.crop,
                        "tile": [crop.tile_row, crop.tile_col],
                        "units": crop.yield_units,
                        "product": crop.crop,
                        "value": crop.yield_units * rules["base_sell_price"],
                    })
            else:
                # Ongoing crop: produce at every interval after maturity
                next_turn = crop.next_production_turn
                if next_turn is None:
                    continue
                while next_turn is not None and next_turn <= horizon:
                    events.append({
                        "turn": next_turn,
                        "crop": crop.crop,
                        "tile": [crop.tile_row, crop.tile_col],
                        "units": crop.yield_units,
                        "product": crop.crop,
                        "value": crop.yield_units * rules["base_sell_price"],
                    })
                    interval = rules.get("ongoing_interval")
                    if interval:
                        next_turn = next_turn + interval
                    else:
                        break

        return sorted(events, key=lambda e: e["turn"])

    def forecast_animals(
        self,
        animals: list[AnimalState],
        current_turn: int,
        horizon: int,
    ) -> list[dict]:
        """Generate dated animal production events through the horizon."""
        events = []
        for animal in animals:
            if not animal.is_alive or animal.location != "PLACED":
                continue
            rules = cfg.ANIMAL_RULES[animal.kind]
            next_turn = animal.next_product_turn
            if next_turn is None:
                continue
            while next_turn <= horizon:
                events.append({
                    "turn": next_turn,
                    "animal_id": animal.animal_id,
                    "kind": animal.kind,
                    "product": rules["product"],
                    "units": rules["product_units"],
                    "value": rules["product_units"] * rules["sell_price"],
                })
                next_turn += rules["product_interval"]

        return sorted(events, key=lambda e: e["turn"])

    def full_forecast(
        self,
        crops: list[CropState],
        animals: list[AnimalState],
        current_turn: int,
        horizon: int,
    ) -> ProductionForecast:
        """Combined crop + animal forecast."""
        crop_events = self.forecast_crops(crops, current_turn, horizon)
        animal_events = self.forecast_animals(animals, current_turn, horizon)

        total_by_product: dict[str, int] = {}
        total_value = 0.0

        for e in crop_events + animal_events:
            p = e["product"]
            total_by_product[p] = total_by_product.get(p, 0) + e["units"]
            total_value += e["value"]

        return ProductionForecast(
            crop_events=crop_events,
            animal_events=animal_events,
            total_by_product=total_by_product,
            total_value=total_value,
        )
