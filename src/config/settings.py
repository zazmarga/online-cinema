import os

from pydantic_settings import BaseSettings

from pathlib import Path


class BaseAppSettings(BaseSettings):
    BASE_DIR: Path = Path(__file__).parent.parent
    PATH_TO_DB: str = str(BASE_DIR / "database" / "source" / "cinema.db")
    PATH_TO_DATA_MOVIES_CSV: str = str(
        BASE_DIR / "database" / "seed_data" / "movies.csv"
    )
    PATH_TO_TEST_MOVIES_CSV: str = str(
        BASE_DIR / "database" / "seed_data" / "test_data.csv"
    )

    PATH_TO_EMAIL_TEMPLATES_DIR: str = str(BASE_DIR / "notifications" / "templates")
    ACTIVATION_EMAIL_TEMPLATE_NAME: str = "activation_request.html"
    ACTIVATION_COMPLETE_EMAIL_TEMPLATE_NAME: str = "activation_complete.html"
    ACTIVATION_RESTORE_EMAIL_TEMPLATE_NAME: str = "activation_restore.html"
    PASSWORD_RESET_TEMPLATE_NAME: str = "password_reset_request.html"
    PASSWORD_RESET_COMPLETE_TEMPLATE_NAME: str = "password_reset_complete.html"
    LIKE_REPLY_NOTIFICATION_EMAIL_TEMPLATE_NAME: str = "like_reply_notification.html"
    PAYMENT_CONFIRMATION_TEMPLATE_NAME: str = "payment_confirmation.html"

    EMAIL_HOST: str = os.getenv("EMAIL_HOST", "localhost")
    EMAIL_PORT: int = int(os.getenv("EMAIL_PORT", 1025))
    EMAIL_HOST_USER: str = os.getenv("EMAIL_HOST_USER", "testuser")
    EMAIL_HOST_PASSWORD: str = os.getenv("EMAIL_HOST_PASSWORD", "test_password")
    EMAIL_USE_TLS: bool = os.getenv("EMAIL_USE_TLS", "False").lower() == "true"
    MAILHOG_API_PORT: int = os.getenv("MAILHOG_API_PORT", 8025)

    LOGIN_TIME_DAYS: int = 7

    CELERY_BROKER: str = os.getenv("CELERY_BROKER", "redis://localhost:6379/0")
    CELERY_BACKEND: str = os.getenv("CELERY_BACKEND", "redis://localhost:6379/0")

    STRIPE_SECRET_KEY: str = os.getenv(
        "STRIPE_SECRET_KEY",
        "<your sk_test_..>",
    )
    STRIPE_PUBLISHABLE_KEY: str = os.getenv(
        "STRIPE_PUBLISHABLE_KEY",
        "<your pk_test_..>",
    )
    BASE_URL: str = os.getenv("BASE_URL", "http://127.0.0.1:4242")
    WEBHOOK_SECRET: str = os.getenv(
        "WEBHOOK_SECRET",
        "<your whsec_..>",
    )

    S3_STORAGE_HOST: str = os.getenv("MINIO_HOST", "127.0.0.1")
    S3_STORAGE_PORT: int = os.getenv("MINIO_PORT", 9000)
    S3_STORAGE_ACCESS_KEY: str = os.getenv("MINIO_ROOT_USER", "minioadmin")
    S3_STORAGE_SECRET_KEY: str = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
    S3_BUCKET_NAME: str = os.getenv("MINIO_STORAGE", "cinema-storage")

    @property
    def S3_STORAGE_ENDPOINT(self) -> str:
        return f"http://{self.S3_STORAGE_HOST}:{self.S3_STORAGE_PORT}"


class Settings(BaseAppSettings):
    SECRET_KEY_ACCESS: str = os.getenv("SECRET_KEY_ACCESS", os.urandom(32).hex())
    SECRET_KEY_REFRESH: str = os.getenv("SECRET_KEY_REFRESH", os.urandom(32).hex())
    JWT_SIGNING_ALGORITHM: str = os.getenv("JWT_SIGNING_ALGORITHM", "HS256")


class TestingSettings(Settings):
    S3_STORAGE_HOST: str = os.getenv("MINIO_HOST", "127.0.0.1")
    S3_STORAGE_PORT: int = os.getenv("MINIO_PORT", 9000)
    S3_STORAGE_ACCESS_KEY: str = os.getenv("MINIO_ROOT_USER", "minioadmin")
    S3_STORAGE_SECRET_KEY: str = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
    S3_BUCKET_NAME: str = os.getenv("MINIO_STORAGE", "cinema-storage")


settings = Settings()
