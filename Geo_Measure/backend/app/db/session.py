"""Engine and session factory construction.

There is no module-level engine or session. The application creates one engine
per process in its lifespan and stores the session factory on ``app.state``;
request handlers receive a short-lived session through dependency injection.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


def build_engine(database_url: str, *, echo: bool = False) -> Engine:
    return create_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def ping(engine: Engine) -> None:
    """Raise if the database is unreachable."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
