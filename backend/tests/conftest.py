import os
from typing import Generator
import pytest

# Determine test database URL:
# If TEST_DATABASE_URL is provided, or if local PostgreSQL is reachable, use PostgreSQL with PostGIS.
# Otherwise fallback to in-memory SQLite + SpatiaLite.

DEFAULT_PG_URL = "postgresql+psycopg://gvg:gvg_secret@localhost:5432/gvg_test"
TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", DEFAULT_PG_URL)

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

is_postgres = False
test_engine = None

if not TEST_DB_URL.startswith("sqlite"):
    try:
        candidate_engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
        with candidate_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        test_engine = candidate_engine
        is_postgres = True
        os.environ["DATABASE_URL"] = TEST_DB_URL
    except Exception:
        test_engine = None

if not is_postgres or test_engine is None:
    # Fallback to in-memory SQLite
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def load_spatialite(dbapi_conn, connection_record):
        try:
            dbapi_conn.enable_load_extension(True)
            for ext in ["mod_spatialite", "mod_spatialite.so", "/usr/lib/x86_64-linux-gnu/mod_spatialite.so", "libspatialite.so"]:
                try:
                    dbapi_conn.load_extension(ext)
                    break
                except Exception:
                    pass
        except Exception:
            pass

    with test_engine.connect() as conn:
        try:
            conn.execute(text("SELECT InitSpatialMetaData(1)"))
            conn.commit()
        except Exception:
            pass

os.environ["ENVIRONMENT"] = "test"

from fastapi.testclient import TestClient
from app.core.database import Base, get_db
from app.main import app

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_schema():
    """Ensure database schema and extensions exist at session level."""
    Base.metadata.create_all(bind=test_engine)
    yield
    if not is_postgres:
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Provide a fresh isolated database session for each test function."""
    if is_postgres:
        connection = test_engine.connect()
        transaction = connection.begin()
        session = TestingSessionLocal(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()
            connection.close()
    else:
        Base.metadata.create_all(bind=test_engine)
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()
            Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
