"""Database layer: engine, session factory, and schema bootstrap.

DATABASE_URL controls the backend:
  - unset / local dev  -> sqlite file at ./data/app.db (zero-config)
  - docker-compose     -> postgresql+psycopg2://... (set in docker-compose.yml)

Call init_db() once at API startup to create tables if they don't exist yet.
For production schema changes, use Alembic migrations in migrations/ instead
of relying on create_all beyond the first boot.
"""
import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DATA_DIR / 'app.db'}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    import models  # noqa: F401  (register models on Base.metadata)

    Base.metadata.create_all(bind=engine)
