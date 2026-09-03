import os
from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@lru_cache
def get_engine():
    database_url = os.getenv("DATABASE_URL", "sqlite:///./smart_warehouse.db")
    return create_engine(database_url)


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
