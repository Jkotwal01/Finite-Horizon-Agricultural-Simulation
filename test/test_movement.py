"""
test/test_movement.py — FR-004: BFS movement engine tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from engine.movement import MovementEngine, MovementResult


@pytest.fixture
def engine():
    return MovementEngine()


class TestNonSquareBFS:

    def test_square_board_reachable(self, engine):
        """ST05-A: Same start and target → reachable, distance=0."""
        r = engine.find_path((0, 0), (0, 0), rows=5, cols=5)
        assert r.reachable
        assert r.distance == 0

    def test_simple_path(self, engine):
        """Straight horizontal path."""
        r = engine.find_path((0, 0), (0, 4), rows=5, cols=5)
        assert r.reachable
        assert r.distance == 4
        assert r.next_step == (0, 1)

    def test_non_square_board(self, engine):
        """ST05-B: 3×7 board — target at end is still reachable."""
        r = engine.find_path((0, 0), (2, 6), rows=3, cols=7)
        assert r.reachable
        assert r.distance == 8  # Manhattan: 2+6

    def test_boundary_target(self, engine):
        """Target at corner boundary."""
        r = engine.find_path((0, 0), (4, 4), rows=5, cols=5)
        assert r.reachable

    def test_unreachable_target_out_of_bounds(self, engine):
        """ST05-C: Target out of bounds → not reachable."""
        r = engine.find_path((0, 0), (10, 10), rows=5, cols=5)
        assert not r.reachable
        assert r.next_step is None
        assert r.distance == -1

    def test_locked_tile_wall(self, engine):
        """LOCKED tiles are treated as walls."""
        # Create a wall across col=1 rows 0-4
        locked = {(r, 1) for r in range(5)}
        r = engine.find_path((0, 0), (0, 2), rows=5, cols=5, locked_tiles=locked)
        # Path must go around — possible via rows 1-4 if they're not all locked
        # But we locked all of col 1, so it's unreachable for 1-row path
        # With 5 rows, BFS can go through row 1 etc — but col 1 is fully blocked
        # No path from (0,0) to (0,2) through only col 0 → impossible
        assert not r.reachable

    def test_locked_target(self, engine):
        """Target itself is locked → not reachable."""
        locked = {(2, 2)}
        r = engine.find_path((0, 0), (2, 2), rows=5, cols=5, locked_tiles=locked)
        assert not r.reachable

    def test_path_avoids_locked(self, engine):
        """Path can go around a single locked tile."""
        locked = {(0, 1)}
        r = engine.find_path((0, 0), (0, 2), rows=5, cols=5, locked_tiles=locked)
        assert r.reachable
        # Should find an alternative route (e.g. via row 1)

    def test_first_step_returned(self, engine):
        """Only first step is returned, not full strategy."""
        r = engine.find_path((0, 0), (3, 3), rows=5, cols=5)
        assert r.next_step is not None
        # next_step should be adjacent to start
        start = (0, 0)
        step = r.next_step
        assert abs(step[0] - start[0]) + abs(step[1] - start[1]) == 1
