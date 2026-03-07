from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery = Celery("contributr", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_hijack_root_logger=False,
    include=["app.workers.tasks"],
    beat_schedule={
        "run-project-insights-daily": {
            "task": "schedule_all_project_insights",
            "schedule": crontab(hour=2, minute=0),
        },
    },
)
