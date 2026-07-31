from celery import Celery

from codeteam.config import get_settings

settings = get_settings()
celery_app = Celery(
    "codeteam",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["codeteam.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_time_limit=900,
    task_soft_time_limit=840,
    worker_prefetch_multiplier=1,
)
