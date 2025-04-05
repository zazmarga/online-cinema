from celery import Celery
import src.config.celeryconfig as celeryconfig

from src.config.settings import settings

celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER,
    backend=settings.CELERY_BACKEND,
)

celery_app.conf.update(
    beat_schedule=celeryconfig.beat_schedule,
    broker_url=celeryconfig.broker_url,
    result_backend=celeryconfig.result_backend,
)

celery_app.autodiscover_tasks(["src.tasks"])
