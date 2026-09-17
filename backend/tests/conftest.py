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
        loaded = False
        try:
            dbapi_conn.enable_load_extension(True)
            for ext in ["mod_spatialite", "mod_spatialite.so", "/usr/lib/x86_64-linux-gnu/mod_spatialite.so", "libspatialite.so"]:
                try:
                    dbapi_conn.load_extension(ext)
                    loaded = True
                    break
                except Exception:
                    pass
        except Exception:
            pass

        if not loaded:
            # Fallback mock functions for SQLite when SpatiaLite is not installed
            for fn, num in [
                ("InitSpatialMetaData", 1),
                ("InitSpatialMetaData", 0),
                ("RecoverGeometryColumn", 5),
                ("DiscardGeometryColumn", 2),
                ("CreateSpatialIndex", 2),
                ("DisableSpatialIndex", 2),
            ]:
                try:
                    dbapi_conn.create_function(fn, num, lambda *args: 1)
                except Exception:
                    pass
            try:
                dbapi_conn.create_function("CheckSpatialIndex", 2, lambda *args: None)
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


class AuthTestClient(TestClient):
    def __init__(self, *args, default_token: str = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_token = default_token

    def request(self, method: str, url: str, **kwargs):
        headers = kwargs.get("headers")
        if headers is None:
            headers = {}
        else:
            headers = dict(headers)

        if "Authorization" not in headers and "authorization" not in headers:
            if headers.get("X-No-Auth") == "1":
                headers.pop("X-No-Auth", None)
            else:
                url_str = str(url)
                if not ("/api/v1/auth/" in url_str) and self.default_token:
                    headers["Authorization"] = f"Bearer {self.default_token}"
        elif headers.get("Authorization") is None:
            headers.pop("Authorization", None)

        kwargs["headers"] = headers
        return super().request(method, url, **kwargs)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a TestClient with overridden get_db dependency and default superadmin auth."""
    from app.models.user import User, UserRole
    from app.core.security import hash_password, create_access_token

    # Ensure a default superadmin user exists for tests
    default_superadmin = (
        db_session.query(User)
        .filter(User.email == "test_superadmin@example.com")
        .first()
    )
    if not default_superadmin:
        default_superadmin = User(
            email="test_superadmin@example.com",
            hashed_password=hash_password("SuperAdmin123!"),
            role=UserRole.SUPER_ADMIN,
            is_active=True,
        )
        db_session.add(default_superadmin)
        db_session.commit()
        db_session.refresh(default_superadmin)

    default_token = create_access_token(
        data={
            "sub": str(default_superadmin.id),
            "role": str(default_superadmin.role),
            "email": default_superadmin.email,
        }
    )

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with AuthTestClient(app, default_token=default_token) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function", autouse=True)
def bind_services_session(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """
    Ensure email_service and broadcast_service share the test database transaction,
    preventing SQLite in-memory threading table isolation errors.
    """
    try:
        from app.services import email_service
        monkeypatch.setattr(
            email_service,
            "get_session",
            lambda db=None: (db or db_session, False),
        )
    except Exception:
        pass
    try:
        from app.services import broadcast_service
        monkeypatch.setattr(
            broadcast_service,
            "get_session",
            lambda db=None: (db or db_session, False),
        )
    except Exception:
        pass

