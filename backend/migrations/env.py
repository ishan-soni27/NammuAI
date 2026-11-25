"""Alembic environment: connects migrations to our models and our DATABASE_URL.

- Target metadata is `app.db.models.Base.metadata`, so `--autogenerate` diffs the models
  against the real database.
- The URL comes from app settings (backend/.env or the environment), never alembic.ini.
- `compare_type=True` makes autogenerate notice column type changes (e.g. NUMERIC precision).
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from app.config.settings import get_settings
from app.db.models import Base
from app.db.session import make_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    # Allows `alembic -x url=...` for one-off runs (e.g. a scratch database) without editing .env.
    return context.get_x_argument(as_dictionary=True).get("url") or get_settings().database_url


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL instead of running it (useful for review)."""
    context.configure(
        url=_database_url() or "postgresql+psycopg://",
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the live database in one transaction."""
    # Migrations are one-off; don't keep pooled connections around.
    engine = make_engine(_database_url(), pooled=False)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
