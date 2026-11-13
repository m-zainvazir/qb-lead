from worker.celery_app import app
from worker.tasks import heartbeat


def test_heartbeat_runs_locally() -> None:
    assert heartbeat.run()


def test_beat_schedule_has_heartbeat() -> None:
    assert app.conf.beat_schedule["heartbeat"]["task"] == "worker.tasks.heartbeat"
    assert app.conf.task_acks_late is True
