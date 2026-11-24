"""Database engine and session management."""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from docagent.core.config import settings
from docagent.core.logging import logger
from docagent.database.models import Base

# Database engine initialization
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args=connect_args,
    future=True
)

session_factory = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)


def init_db() -> None:
    """Creates database schema tables if they do not exist."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized successfully.")


def get_db_session() -> Generator[Session, None, None]:
    """Dependency providing a transactional database session."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
