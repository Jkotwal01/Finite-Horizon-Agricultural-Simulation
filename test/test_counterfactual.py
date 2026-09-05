"""
test_counterfactual.py — FR-019 Counterfactual Replanning Verification

Proves the AI uses the Simulator clone feature to run alternatives
and selects the one with higher terminal wealth.
"""
import copy
from backend.engine.simulator import Simulator
from backend.models.task import Task
import backend.config as cfg

def test_counterfactual_replanning_chooses_higher_wealth():
    """
    Provide the simulator with two mocked candidate paths:
    - WAIT (baseline, no strategic actions)
    - HIRE_WORKER (strategic candidate)

    We mock run_n_turns on the clones to return predetermined terminal wealths,
    proving the _run_counterfactuals method selects the candidate if it improves wealth.
    """
    sim = Simulator()
    sim.start(initial_cash=1000.0)

    # We will mock the behavior of deepcopy so we can intercept run_n_turns on the clones.
    # Instead of monkeypatching deepcopy globally, we'll patch run_n_turns on the cloned instances.
    
    # Create dummy tasks
    hire_task = Task(
        task_id="hire_worker_test",
        kind="HIRE",
        priority=cfg.PRIORITY_ECONOMIC,
        value=50.0,
        target=None,
    )
    
    candidates = [[hire_task]]
    
    # We monkeypatch the copy module just for this test
    original_deepcopy = copy.deepcopy
    
    clone_count = [0]
    
    def fake_deepcopy(obj, memo=None):
        cloned = original_deepcopy(obj, memo)
        if isinstance(cloned, Simulator):
            clone_count[0] += 1
            # First clone is baseline, second clone is candidate
            is_baseline = (clone_count[0] == 1)
            
            def fake_run_n_turns(n: int):
                if is_baseline:
                    return {"terminal": {"terminal_wealth": 1500.0}}
                else:
                    return {"terminal": {"terminal_wealth": 1600.0}}
            
            cloned.run_n_turns = fake_run_n_turns
        return cloned
        
    copy.deepcopy = fake_deepcopy
    try:
        best_tasks = sim._run_counterfactuals(candidates, remaining_turns=10)
    finally:
        copy.deepcopy = original_deepcopy
        
    # The candidate (HIRE) improved terminal wealth from 1500 to 1600 (delta 100 > 1.0 threshold).
    # Therefore, bounded_replan should have selected it, returning the hire_task.
    assert len(best_tasks) == 1
    assert best_tasks[0].kind == "HIRE"

def test_counterfactual_replanning_rejects_lower_wealth():
    """
    If the candidate path yields lower terminal wealth than baseline,
    it should be rejected and return an empty task list.
    """
    sim = Simulator()
    sim.start(initial_cash=1000.0)

    hire_task = Task(
        task_id="hire_worker_test", kind="HIRE",
        priority=cfg.PRIORITY_ECONOMIC, value=50.0, target=None,
    )
    candidates = [[hire_task]]
    
    original_deepcopy = copy.deepcopy
    clone_count = [0]
    
    def fake_deepcopy(obj, memo=None):
        cloned = original_deepcopy(obj, memo)
        if isinstance(cloned, Simulator):
            clone_count[0] += 1
            is_baseline = (clone_count[0] == 1)
            
            def fake_run_n_turns(n: int):
                if is_baseline:
                    return {"terminal": {"terminal_wealth": 1500.0}}
                else:
                    # Candidate makes us poorer!
                    return {"terminal": {"terminal_wealth": 1400.0}}
            
            cloned.run_n_turns = fake_run_n_turns
        return cloned
        
    copy.deepcopy = fake_deepcopy
    try:
        best_tasks = sim._run_counterfactuals(candidates, remaining_turns=10)
    finally:
        copy.deepcopy = original_deepcopy
        
    # Should reject the candidate and return nothing
    assert len(best_tasks) == 0
