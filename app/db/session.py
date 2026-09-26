from collections.abc import Generator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings


@lru_cache
def get_engine(database_url: str):
    """Return the cached synchronous engine for a validated database URL."""
    return create_engine(database_url)


def get_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Generator[Session, None, None]:
    """Yield a request-scoped session bound to the configured database."""
    with Session(get_engine(settings.database_url)) as session:
        yield session
