from celery.schedules import crontab

from src.config.settings import settings

beat_schedule = {
    "delete-expired-tokens-twice-a-day": {
        "task": "delete_expired_activation_tokens",
        "schedule": crontab(minute="0", hour="*/12"),  # every 12 hours (twice a day)
    },
}

broker_url = settings.CELERY_BROKER
result_backend = settings.CELERY_BACKEND
