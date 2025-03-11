import pytest
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

settings = TestingSettings()

TEST_DATABASE_URL = f"sqlite:///{settings.PATH_TO_DB}"[:-3] + "_test.db"

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
def jwt_manager(settings):
    return JWTAuthManager(
        secret_key_access=settings.SECRET_KEY_ACCESS,
        secret_key_refresh=settings.SECRET_KEY_REFRESH,
        algorithm=settings.JWT_SIGNING_ALGORITHM,
    )
