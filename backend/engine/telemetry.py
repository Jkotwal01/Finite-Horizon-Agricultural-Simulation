"""
engine/telemetry.py — TelemetryEngine (FR-021).

Records timing, exceptions, invalid actions, forecast errors, and losses.
Produces EvaluationReport.
"""
from __future__ import annotations
import time
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.report import EvaluationReport, TerminalResult
import config as cfg


class TelemetryEngine:
    """
    Records all run events for diagnostics and release gating.
    """

    def __init__(self) -> None:
        self.report = EvaluationReport()
        self._turn_start_time: float = 0.0

    def start_turn(self, turn: int) -> None:
        """Mark the beginning of a turn for timing."""
        self._turn_start_time = time.monotonic()
        self.report.turns = turn

    def end_turn(self, turn: int, wealth: float) -> float:
        """Record turn timing and wealth snapshot. Returns elapsed_ms."""
        elapsed_ms = (time.monotonic() - self._turn_start_time) * 1000
        self.report.timing_ms[str(turn)] = round(elapsed_ms, 2)
        self.report.per_turn_wealth.append(round(wealth, 2))
        return elapsed_ms

    def record_exception(self, turn: int, error: str) -> None:
        self.report.exceptions += 1
        self.report.record_action(turn, {}, "EXCEPTION", error)

    def record_invalid_action(self, turn: int, action: dict, error: str) -> None:
        self.report.invalid_actions += 1
        self.report.record_action(turn, action, "INVALID", error)

    def record_accepted_action(self, turn: int, action: dict) -> None:
        self.report.record_action(turn, action, "ACCEPTED")

    def record_crop_death(self, turn: int, crop_info: dict) -> None:
        self.report.crop_deaths += 1
        self.report.loss_events["crop_deaths"] = self.report.crop_deaths
        self.report.record_action(turn, crop_info, "CROP_DEAD",
                                  f"Crop {crop_info.get('crop')} died at ({crop_info.get('tile_row')},{crop_info.get('tile_col')}).")

    def record_animal_death(self, turn: int, animal_info: dict) -> None:
        self.report.animal_deaths += 1
        self.report.loss_events["animal_deaths"] = self.report.animal_deaths
        self.report.record_action(turn, animal_info, "ANIMAL_DEAD",
                                  f"Animal {animal_info.get('animal_id')} died.")

    def record_warehouse_overflow(self, turn: int) -> None:
        self.report.warehouse_overflows += 1
        self.report.loss_events["warehouse_overflows"] = self.report.warehouse_overflows

    def record_forecast_error(self, domain: str, predicted: float,
                              actual: float) -> None:
        error_pct = abs(predicted - actual) / max(1, actual) * 100
        if domain not in self.report.forecast_error:
            self.report.forecast_error[domain] = []
        self.report.forecast_error[domain].append({
            "predicted": predicted,
            "actual": actual,
            "error_pct": round(error_pct, 1),
        })

    def finalise(self, terminal: TerminalResult) -> EvaluationReport:
        """Attach terminal result to the report and return it."""
        self.report.terminal_wealth = terminal.terminal_wealth
        return self.report

    def release_gate(self) -> dict:
        """
        FR-021 release gate: return pass/fail for each acceptance metric.
        """
        return {
            "exceptions_zero": self.report.exceptions == 0,
            "invalid_actions_zero": self.report.invalid_actions == 0,
            "crop_deaths_zero": self.report.crop_deaths == 0,
            "animal_deaths_zero": self.report.animal_deaths == 0,
            "warehouse_overflows_zero": self.report.warehouse_overflows == 0,
            "all_pass": (
                self.report.exceptions == 0 and
                self.report.invalid_actions == 0
            ),
        }
