"""
engine/movement.py — MovementEngine using BFS (FR-004).

Finds the legal first step toward a target on a 2-D grid.
LOCKED tiles are treated as walls.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from typing import Optional


@dataclass
class MovementResult:
    """Result of one movement calculation."""
    reachable: bool
    next_step: Optional[tuple[int, int]]   # (row, col) of the first legal step
    distance: int                           # BFS distance to target
    path: list[tuple[int, int]]            # full path from start to target


class MovementEngine:
    """
    BFS-based movement engine.

    Rules (FR-004):
    - Uses actual row/col dimensions (non-square board supported).
    - Locked tiles are impassable.
    - Returns the first legal step, not the entire strategy.
    """

    def find_path(
        self,
        start: tuple[int, int],
        target: tuple[int, int],
        rows: int,
        cols: int,
        locked_tiles: set[tuple[int, int]] | None = None,
    ) -> MovementResult:
        """
        BFS from start to target on a rows×cols grid.

        Parameters
        ----------
        start         : (row, col) of the worker
        target        : (row, col) destination
        rows, cols    : board dimensions
        locked_tiles  : set of (row, col) that cannot be traversed
        """
        if locked_tiles is None:
            locked_tiles = set()

        # Boundary check
        if not self._in_bounds(target, rows, cols):
            return MovementResult(reachable=False, next_step=None, distance=-1, path=[])

        if target in locked_tiles:
            return MovementResult(reachable=False, next_step=None, distance=-1, path=[])

        if start == target:
            return MovementResult(reachable=True, next_step=target, distance=0, path=[target])

        # Standard BFS
        queue: deque[tuple[tuple[int, int], list]] = deque()
        queue.append((start, [start]))
        visited: set[tuple[int, int]] = {start}

        while queue:
            current, path = queue.popleft()
            for neighbor in self._neighbors(current, rows, cols, locked_tiles, visited):
                new_path = path + [neighbor]
                if neighbor == target:
                    first_step = new_path[1] if len(new_path) > 1 else target
                    return MovementResult(
                        reachable=True,
                        next_step=first_step,
                        distance=len(new_path) - 1,
                        path=new_path,
                    )
                visited.add(neighbor)
                queue.append((neighbor, new_path))

        return MovementResult(reachable=False, next_step=None, distance=-1, path=[])

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _in_bounds(pos: tuple[int, int], rows: int, cols: int) -> bool:
        r, c = pos
        return 0 <= r < rows and 0 <= c < cols

    def _neighbors(
        self,
        pos: tuple[int, int],
        rows: int,
        cols: int,
        locked: set,
        visited: set,
    ) -> list[tuple[int, int]]:
        r, c = pos
        candidates = [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]
        return [
            n for n in candidates
            if self._in_bounds(n, rows, cols) and n not in locked and n not in visited
        ]
