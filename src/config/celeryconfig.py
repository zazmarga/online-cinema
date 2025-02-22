from celery.schedules import crontab

from src.config.settings import settings

beat_schedule = {
    "delete-expired-tokens-every-hour": {
        "task": "delete_expired_activation_tokens",
        "schedule": crontab(hour="*/1"),  # every hour
    },
}

broker_url = settings.CELERY_BROKER
result_backend = settings.CELERY_BACKEND
