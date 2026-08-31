from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


engine = create_engine(
    settings.database_url,
)


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    """
    Timezone-AWARE current UTC time.

    Use this instead of datetime.utcnow() as a column default.
    datetime.utcnow() returns a naive datetime — when inserted
    into a TIMESTAMP WITH TIME ZONE column, Postgres assumes a
    naive value is in the *session's* local timezone, not UTC,
    silently shifting stored timestamps by the session's UTC
    offset. Passing an aware datetime avoids that ambiguity.
    """

    return datetime.now(timezone.utc)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()