from sqlalchemy import create_engine, pool

from alembic import context
from app.core.config import get_settings

config = context.config


def run_migrations_online() -> None:
    engine = create_engine(
        get_settings().sqlalchemy_url,
        poolclass=pool.NullPool,
        connect_args={"prepare_threshold": None},
    )
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Offline mode is not supported: the migrations run SQL files.")
run_migrations_online()
