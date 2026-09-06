import os
import tempfile
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect


def test_alembic_migrations_upgrade_and_downgrade():
    """Verify that Alembic migrations run cleanly from base to head and downgrade back to base."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        from pathlib import Path
        root_backend = Path(__file__).resolve().parent.parent
        db_url = f"sqlite:///{db_path}"
        ini_path = str(root_backend / "alembic.ini")
        alembic_cfg = Config(ini_path)
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        alembic_cfg.set_main_option("script_location", str(root_backend / "alembic"))

        # 1. Execute upgrade head
        command.upgrade(alembic_cfg, "head")

        # Verify table 'events' and columns exist
        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "events" in tables, f"Expected 'events' table in {tables}"

        columns = [c["name"] for c in inspector.get_columns("events")]
        assert "id" in columns
        assert "slug" in columns
        assert "title" in columns
        assert "price_per_meter_cents" in columns
        assert "map_type" in columns
        assert "status" in columns

        # 2. Execute downgrade to base
        command.downgrade(alembic_cfg, "base")
        inspector = inspect(engine)
        assert "events" not in inspector.get_table_names()
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
