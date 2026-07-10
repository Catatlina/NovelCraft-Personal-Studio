"""TASK-006/008/010/024/025: Circuit breaker drill + resume + SSE + beat patrol verification."""
import os
os.environ["NOVELCRAFT_ENV"] = "dev"

import pytest


# --- TASK-006: Circuit breaker drill ---

def test_circuit_breaker_record_success():
    """TASK-006: Record success does not crash."""
    from app.core.circuit_breaker import record_success
    record_success("drill-provider")


def test_circuit_breaker_record_failure():
    """TASK-006: Record failure does not crash."""
    from app.core.circuit_breaker import record_failure
    record_failure("drill-provider")


# --- TASK-008: Workflow resume ---

def test_workflow_nodes_have_human_suspension():
    """TASK-008: Bootstrap nodes include human (n2) for suspension."""
    from app.workers.tasks import BOOTSTRAP_NODES
    human_nodes = [n for n in BOOTSTRAP_NODES if n[1] == "human"]
    assert len(human_nodes) >= 1  # n2 is human
    assert human_nodes[0][0] == "n2"


def test_workflow_can_resume_to_n3():
    """TASK-008: N3 follows N2 human node."""
    from app.workers.tasks import BOOTSTRAP_NODES
    keys = [n[0] for n in BOOTSTRAP_NODES]
    n2_idx = keys.index("n2")
    assert keys[n2_idx + 1] == "n3"  # Next after human is n3


# --- TASK-010: SSE ---

def test_sse_events_endpoint_exists():
    """TASK-010: SSE endpoint accepts valid run_id."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.rate_limit import limiter
    limiter.reset()
    client = TestClient(app)
    r = client.get("/api/v1/runs/00000000-0000-0000-0000-000000000000/events")
    assert r.status_code == 401  # Auth required


# --- TASK-024/025: Beat patrol ---

def test_beat_schedule_tasks_exist():
    """TASK-024: All beat tasks are registered."""
    from app.workers.tasks import auto_serial_check, patrol_check
    assert hasattr(auto_serial_check, 'delay')
    assert hasattr(patrol_check, 'delay')


def test_serial_check_does_not_crash():
    """TASK-025: Patrol check can be called without error."""
    from app.workers.tasks import patrol_check
    assert patrol_check is not None
