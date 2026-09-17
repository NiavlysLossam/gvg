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
        assert "spots" in tables, f"Expected 'spots' table in {tables}"
        assert "orders" in tables, f"Expected 'orders' table in {tables}"
        assert "booking_items" in tables, f"Expected 'booking_items' table in {tables}"
        assert "email_logs" in tables, f"Expected 'email_logs' table in {tables}"
        assert "users" in tables, f"Expected 'users' table in {tables}"

        columns = [c["name"] for c in inspector.get_columns("events")]
        assert "id" in columns
        assert "slug" in columns
        assert "title" in columns
        assert "price_per_meter_cents" in columns
        assert "map_type" in columns
        assert "status" in columns
        assert "center_latitude" in columns
        assert "center_longitude" in columns
        assert "default_zoom" in columns
        assert "owner_id" in columns

        user_columns = [c["name"] for c in inspector.get_columns("users")]
        assert "id" in user_columns
        assert "email" in user_columns
        assert "hashed_password" in user_columns
        assert "role" in user_columns
        assert "is_active" in user_columns

        spot_columns = [c["name"] for c in inspector.get_columns("spots")]
        assert "id" in spot_columns
        assert "event_id" in spot_columns
        assert "label" in spot_columns
        assert "linear_meters" in spot_columns
        assert "price_cents" in spot_columns
        assert "geom" in spot_columns
        assert "status" in spot_columns
        assert "locked_until" in spot_columns
        assert "locked_by_token" in spot_columns

        order_columns = [c["name"] for c in inspector.get_columns("orders")]
        assert "id" in order_columns
        assert "event_id" in order_columns
        assert "order_number" in order_columns
        assert "first_name" in order_columns
        assert "last_name" in order_columns
        assert "email" in order_columns
        assert "phone" in order_columns
        assert "street_address" in order_columns
        assert "postal_code" in order_columns
        assert "city" in order_columns
        assert "honor_declaration_accepted" in order_columns
        assert "honor_declaration_accepted_at" in order_columns
        assert "total_price_cents" in order_columns
        assert "status" in order_columns
        assert "access_token" in order_columns
        assert "offline_payment_reference" in order_columns
        assert "admin_notes" in order_columns
        assert "cancellation_reason" in order_columns
        assert "cancellation_comment" in order_columns
        assert "cancellation_requested_at" in order_columns

        booking_columns = [c["name"] for c in inspector.get_columns("booking_items")]
        assert "id" in booking_columns
        assert "order_id" in booking_columns
        assert "spot_id" in booking_columns
        assert "price_cents" in booking_columns

        # 2. Execute downgrade to base
        command.downgrade(alembic_cfg, "base")
        inspector = inspect(engine)
        assert "events" not in inspector.get_table_names()
        assert "spots" not in inspector.get_table_names()
        assert "orders" not in inspector.get_table_names()
        assert "booking_items" not in inspector.get_table_names()
        assert "email_logs" not in inspector.get_table_names()
        assert "users" not in inspector.get_table_names()
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
