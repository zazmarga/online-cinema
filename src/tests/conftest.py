import subprocess

import pytest
import requests
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from src.config.dependencies import get_settings
from src.config.settings import TestingSettings
from src.database.models.accounts import UserGroupEnum, UserGroupModel
from src.database.models.base import Base

from src.database.session import get_db
from src.main import app
from src.security.token_manager import JWTAuthManager
from minio import Minio
from minio.error import S3Error


test_settings = TestingSettings()

TEST_DATABASE_URL = f"sqlite:///{test_settings.PATH_TO_DB}"[:-3] + "_test.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module")
def db_session():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


# get_db
@pytest.fixture(autouse=True)
def override_get_db(db_session):
    # get_db for tests
    app.dependency_overrides[get_db] = lambda: db_session


@pytest.fixture(autouse=True)
def client():
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def cleanup_db():
    yield
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture(scope="function")
def seed_user_groups(db_session):
    groups = [{"name": group.value} for group in UserGroupEnum]
    db_session.execute(insert(UserGroupModel).values(groups))
    db_session.commit()
    yield db_session


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="function")
def jwt_manager(settings) -> JWTAuthManager:
    return JWTAuthManager(
        secret_key_access=settings.SECRET_KEY_ACCESS,
        secret_key_refresh=settings.SECRET_KEY_REFRESH,
        algorithm=settings.JWT_SIGNING_ALGORITHM,
    )


@pytest.fixture(scope="module")
def minio_client():
    minio_host_port = f"{test_settings.S3_STORAGE_HOST}:{test_settings.S3_STORAGE_PORT}"
    access_key = test_settings.S3_STORAGE_ACCESS_KEY
    secret_key = test_settings.S3_STORAGE_SECRET_KEY
    bucket_name = test_settings.S3_BUCKET_NAME

    client = Minio(
        minio_host_port,
        access_key=access_key,
        secret_key=secret_key,
        secure=False,
    )

    # create bucket if it does not exist
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)

    yield client

    # clean after test
    try:
        objects = client.list_objects(bucket_name, prefix="avatars/", recursive=True)
        for obj in objects:
            client.remove_object(bucket_name, obj.object_name)
        print("Storage cleaned successfully.")
    except S3Error as e:
        print(f"Error during cleanup: {e}")


@pytest.fixture(scope="function")
def seed_database(db_session, settings):
    from src.database.populate import CSVDatabaseSeeder

    seeder = CSVDatabaseSeeder(
        csv_file_path=settings.PATH_TO_MOVIES_CSV, db_session=db_session
    )
    if not seeder.is_db_populated():
        seeder.seed()
    yield db_session


def restart_mailhog():
    try:
        subprocess.run(["docker", "restart", "mailhog"], check=True)
        print("MailHog has been restarted successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to restart MailHog: {e}")


@pytest.fixture(scope="function", autouse=True)
def cleanup_mailhog():
    yield
    restart_mailhog()
