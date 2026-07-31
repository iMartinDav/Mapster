"""SQLAlchemy engine, session factory, and declarative base."""

from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from mapster.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    return _engine


def get_engine():
    """Public accessor for the shared SQLAlchemy engine (e.g. for GeoPandas to_postgis/read_postgis)."""
    return _get_engine()


def _get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine(), expire_on_commit=False)
    return _SessionLocal


def get_session():
    """FastAPI dependency that yields a DB session."""
    db = _get_session_factory()()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope():
    """Plain context-manager session, for use outside FastAPI request handlers."""
    db = _get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables and the PostGIS extension (called once at startup)."""
    engine = _get_engine()
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    except Exception as e:
        print(f"Warning: could not enable PostGIS extension: {e}")
    Base.metadata.create_all(bind=engine)
