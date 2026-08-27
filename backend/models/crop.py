"""
models/crop.py — CropState data class.

FR-005: Crop lifecycle (plant, water, fertilize, harvest).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CropState:
    """
    Tracks a single crop planted on a tile.

    Fields match the FRD minimum schema (Section 8):
        crop, planted_turn, age, water_status, fertilized,
        yield_units, next_production_turn
    """
    crop: str                          # "WHEAT", "TOMATO", "STRAWBERRY"
    tile_row: int
    tile_col: int
    planted_turn: int
    age: int = 0                       # turns since planting
    water_status: str = "OK"          # "OK" | "MISSED_1" | "DEAD"
    consecutive_missed_water: int = 0
    fertilized: bool = False
    yield_units: int = 0               # set from CROP_RULES on creation
    base_yield: int = 0
    next_production_turn: Optional[int] = None
    is_mature: bool = False
    is_dead: bool = False
    harvest_count: int = 0             # for ongoing crops

    def to_dict(self) -> dict:
        return {
            "crop": self.crop,
            "tile_row": self.tile_row,
            "tile_col": self.tile_col,
            "planted_turn": self.planted_turn,
            "age": self.age,
            "water_status": self.water_status,
            "consecutive_missed_water": self.consecutive_missed_water,
            "fertilized": self.fertilized,
            "yield_units": self.yield_units,
            "next_production_turn": self.next_production_turn,
            "is_mature": self.is_mature,
            "is_dead": self.is_dead,
            "harvest_count": self.harvest_count,
        }
