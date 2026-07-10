"""TASK-024/025: Beat schedule + patrol check verification."""
import os
os.environ["NOVELCRAFT_ENV"] = "dev"


def test_beat_schedule_config():
    """TASK-024: Verify beat schedule module loads and tasks are registered."""
    from app.workers.celery_app import celery_app
    schedule = celery_app.conf.beat_schedule
    assert "auto-serial-check" in schedule
    assert "patrol-check" in schedule


def test_beat_tasks_importable():
    """TASK-024: All beat tasks can be imported."""
    from app.workers.tasks import auto_serial_check, patrol_check
    assert auto_serial_check is not None
    assert patrol_check is not None
