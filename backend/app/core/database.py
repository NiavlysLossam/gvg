from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings

# Determine connect args based on DB engine
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

if settings.DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event, text
    @event.listens_for(engine, "connect")
    def _load_spatialite(dbapi_conn, connection_record):
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

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a SQLAlchemy database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

