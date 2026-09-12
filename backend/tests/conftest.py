import os
from typing import Generator
import pytest

# Ensure tests use in-memory SQLite
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ENVIRONMENT"] = "test"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app

# In-memory SQLite with StaticPool
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

# Initialize spatial metadata for SpatiaLite if present
with test_engine.connect() as conn:
    try:
        conn.execute(text("SELECT InitSpatialMetaData(1)"))
        conn.commit()
    except Exception:
        pass

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Create a fresh database schema for each test function."""
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

