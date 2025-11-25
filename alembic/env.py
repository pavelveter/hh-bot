from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from bot.config import settings
from bot.db.models import Base

# Alembic Config
config = context.config

# Logging config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_sync_url():
    """
    Alembic works ONLY with the sync SQLAlchemy engine.
    So we need a sync URL even if the application itself is async.
    Neon provides the URL in postgres:// format → it must be converted.
    """

    url = settings.DATABASE_URL

    if not url:
        raise RuntimeError("DATABASE_URL is missing in environment variables")

    # Neon typically gives: postgres://user...
    # Convert to sync-compatible URL:
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)

    # If async URL accidentally passed → convert:
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)

    return url


def run_migrations_offline():
    """Run migrations without DB connection."""
    url = get_sync_url()

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations with sync SQLAlchemy engine."""
    config_section = config.get_section(config.config_ini_section)
    config_section["sqlalchemy.url"] = get_sync_url()

    connectable = engine_from_config(
        config_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# Entry point
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
