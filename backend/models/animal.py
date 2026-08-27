"""
models/animal.py — AnimalState data class.

FR-008: Animal lifecycle (buy, transit, carry, place, produce, feed).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class AnimalState:
    """
    Tracks a single animal from purchase through production.

    Locations: "SHED" | "CARRIED" | "PLACED" | "TRANSIT"
    """
    animal_id: str                         # unique id e.g. "cow_0"
    kind: str                              # "COW" | "CHICKEN"
    location: str = "SHED"               # see above
    tile_row: Optional[int] = None        # set when PLACED
    tile_col: Optional[int] = None
    carried_by: Optional[int] = None      # worker index
    fed: bool = True
    consecutive_missed_feed: int = 0
    is_alive: bool = True
    next_product_turn: Optional[int] = None
    product_ready: int = 0                # units waiting to be collected
    placed_turn: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "animal_id": self.animal_id,
            "kind": self.kind,
            "location": self.location,
            "tile_row": self.tile_row,
            "tile_col": self.tile_col,
            "carried_by": self.carried_by,
            "fed": self.fed,
            "consecutive_missed_feed": self.consecutive_missed_feed,
            "is_alive": self.is_alive,
            "next_product_turn": self.next_product_turn,
            "product_ready": self.product_ready,
        }
