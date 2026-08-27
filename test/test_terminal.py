"""
test/test_terminal.py — FR-022: Terminal result / ledger tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from models.report import TerminalResult


class TestTerminalLedger:

    def test_terminal_wealth_computation(self):
        """ST01-A: terminal_wealth = cash + inventory + assets - penalties."""
        t = TerminalResult(
            turn=720,
            cash=1000.0,
            inventory_value=500.0,
            asset_value=200.0,
            penalties=50.0,
        )
        wealth = t.compute()
        assert abs(wealth - 1650.0) < 0.01

    def test_unrealizable_excluded(self):
        """Unrealizable production does NOT add to terminal_wealth."""
        t = TerminalResult(
            turn=720,
            cash=1000.0,
            inventory_value=200.0,
            unrealizable_production=500.0,  # should be ignored
        )
        wealth = t.compute()
        assert abs(wealth - 1200.0) < 0.01

    def test_deterministic_same_state_twice(self):
        """ST01-F: Same inputs → same terminal_wealth (deterministic)."""
        t1 = TerminalResult(turn=720, cash=500.0, inventory_value=100.0)
        t2 = TerminalResult(turn=720, cash=500.0, inventory_value=100.0)
        assert t1.compute() == t2.compute()

    def test_component_ledger_populated(self):
        """component_ledger contains all keys after compute()."""
        t = TerminalResult(turn=720, cash=300.0, inventory_value=150.0, penalties=20.0)
        t.compute()
        assert "cash" in t.component_ledger
        assert "inventory_value" in t.component_ledger
        assert "penalties" in t.component_ledger
        assert "terminal_wealth" in t.component_ledger

    def test_penalty_reduces_wealth(self):
        """Penalties are subtracted from terminal wealth."""
        t_no_penalty = TerminalResult(turn=720, cash=500.0, penalties=0.0)
        t_with_penalty = TerminalResult(turn=720, cash=500.0, penalties=100.0)
        assert t_no_penalty.compute() > t_with_penalty.compute()

    def test_to_dict_rounds_values(self):
        """to_dict returns rounded values for clean JSON output."""
        t = TerminalResult(turn=720, cash=333.333333, inventory_value=66.666666)
        t.compute()
        d = t.to_dict()
        assert d["cash"] == 333.33
        assert d["inventory_value"] == 66.67

    def test_zero_wealth_case(self):
        """ST01-C: Failure case — all zeros still produces valid result."""
        t = TerminalResult(turn=0, cash=0.0)
        wealth = t.compute()
        assert wealth == 0.0

    def test_exceptions_tracked(self):
        """Exceptions and invalid_actions are recorded in terminal result."""
        t = TerminalResult(turn=720, cash=100.0, exceptions=3, invalid_actions=5)
        t.compute()
        d = t.to_dict()
        assert d["exceptions"] == 3
        assert d["invalid_actions"] == 5
