"""
test/test_animals.py — FR-008, FR-009: Animal lifecycle and care tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from engine.animal_manager import AnimalManager
import config as cfg


@pytest.fixture
def mgr():
    m = AnimalManager()
    m.build_structure("BARN")
    m.build_structure("COOP")
    return m


class TestAnimalTransit:

    def test_buy_without_structure_raises(self):
        """ST09-C: No structure → cannot buy animal."""
        m = AnimalManager()  # no structure built
        with pytest.raises(ValueError, match="Missing structure"):
            m.buy_animal("COW", worker_id=0)

    def test_buy_cow_in_carried_state(self, mgr):
        """ST09-A: Purchase → animal appears as CARRIED by worker."""
        animal = mgr.buy_animal("COW", worker_id=0)
        assert animal.location == "CARRIED"
        assert animal.carried_by == 0

    def test_place_animal_after_carry(self, mgr):
        """Animal can only be placed after being carried (ST09-D)."""
        animal = mgr.buy_animal("COW", worker_id=0)
        result = mgr.place_animal(animal.animal_id, row=2, col=2, current_turn=10)
        assert result is True
        assert animal.location == "PLACED"
        assert animal.tile_row == 2

    def test_cannot_place_non_carried(self, mgr):
        """Cannot place an animal that isn't being carried."""
        animal = mgr.buy_animal("COW", worker_id=0)
        mgr.place_animal(animal.animal_id, 0, 0, current_turn=1)
        # Try to place again
        result = mgr.place_animal(animal.animal_id, 1, 1, current_turn=2)
        assert result is False

    def test_duplicate_purchase_prevention(self, mgr):
        """BR-004: count_all_animals includes carried animals."""
        mgr.buy_animal("COW", worker_id=0)
        count = mgr.count_all_animals("COW")
        assert count == 1

    def test_unknown_animal_raises(self, mgr):
        with pytest.raises(ValueError, match="Unknown animal kind"):
            mgr.buy_animal("DRAGON", worker_id=0)


class TestDailyFeed:

    def test_feed_task_generated(self, mgr):
        """ST10-A: Unfed placed animal → feed task at PRIORITY_SURVIVAL."""
        animal = mgr.buy_animal("CHICKEN", worker_id=0)
        mgr.place_animal(animal.animal_id, 1, 1, current_turn=1)
        # Advance one turn without feeding → animal.fed = False
        mgr.advance_turn(2)
        tasks = mgr.generate_feed_tasks()
        assert len(tasks) == 1
        assert tasks[0].priority == cfg.PRIORITY_SURVIVAL
        assert tasks[0].kind == "FEED"

    def test_two_missed_feeds_kills_animal(self, mgr):
        """Missing 2 consecutive feeds → animal dies."""
        animal = mgr.buy_animal("CHICKEN", worker_id=0)
        mgr.place_animal(animal.animal_id, 1, 1, current_turn=1)
        events_all = []
        for t in range(2, 5):  # no feeding
            events_all.extend(mgr.advance_turn(t))
        dead = [e for e in events_all if e["type"] == "ANIMAL_DEAD"]
        assert len(dead) >= 1
        assert not animal.is_alive

    def test_feeding_prevents_death(self, mgr):
        """Feeding each turn keeps the animal alive."""
        animal = mgr.buy_animal("COW", worker_id=0)
        mgr.place_animal(animal.animal_id, 0, 0, current_turn=1)
        for t in range(2, 10):
            mgr.feed_animal(animal.animal_id)
            mgr.advance_turn(t)
        assert animal.is_alive

    def test_product_collected(self, mgr):
        """After product_interval turns, product is collectible."""
        animal = mgr.buy_animal("CHICKEN", worker_id=0)
        mgr.place_animal(animal.animal_id, 0, 0, current_turn=1)
        # Feed and advance past product_interval (12 turns)
        for t in range(2, 15):
            mgr.feed_animal(animal.animal_id)
            mgr.advance_turn(t)
        product, units = mgr.collect_product(animal.animal_id)
        assert product == "EGGS"
        assert units > 0

    def test_multiple_animals_multiple_feed_tasks(self, mgr):
        """Multiple unfed animals → multiple feed tasks."""
        a1 = mgr.buy_animal("CHICKEN", worker_id=0)
        a2 = mgr.buy_animal("CHICKEN", worker_id=1)
        mgr.place_animal(a1.animal_id, 0, 0, 1)
        mgr.place_animal(a2.animal_id, 0, 1, 1)
        mgr.advance_turn(2)  # both unfed now
        tasks = mgr.generate_feed_tasks()
        assert len(tasks) == 2
