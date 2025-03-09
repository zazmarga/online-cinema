import pytest
from fastapi.testclient import TestClient
from src.config.dependencies import (
    get_settings,
    get_accounts_email_notificator,
    get_s3_storage_client,
)
from src.main import app


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="function")
def client(email_sender_stub, s3_storage_fake):
    app.dependency_overrides[get_accounts_email_notificator] = lambda: email_sender_stub
    app.dependency_overrides[get_s3_storage_client] = lambda: s3_storage_fake

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
