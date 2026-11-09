from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from sqlalchemy import Connection, DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

SQL_DIR = Path(__file__).resolve().parents[2] / "db"


class Base(DeclarativeBase):
    # Every timestamp in the database is timestamptz.
    type_annotation_map = {datetime: DateTime(timezone=True)}
    __mapper_args__ = {"eager_defaults": True}


def make_engine(url: str | None = None):
    settings = get_settings()
    return create_engine(
        url or settings.sqlalchemy_url,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,  # the database may have been suspended while idle
        pool_recycle=240,
        # Works with connection poolers (PgBouncer) as well as direct connections.
        connect_args={"prepare_threshold": None},
    )


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=True)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run_sql_file(connection: Connection, name: str) -> None:
    """Run a whole .sql file in the current transaction.

    The file is sent to the driver as one script, so functions that contain
    semicolons (PL/pgSQL) do not need to be split.
    """
    script = (SQL_DIR / name).read_text(encoding="utf-8")
    connection.connection.driver_connection.execute(script)
