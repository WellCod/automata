from collections.abc import Generator
from functools import lru_cache
from typing import Annotated

from agno.db.postgres import PostgresDb
from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.settings import get_settings


def get_db() -> PostgresDb:
    # o engine da API: com db_url cada chamada abria um pool novo, nunca descartado (Fase 44)
    return PostgresDb(db_engine=get_engine())


@lru_cache(maxsize=1)
def _build_engine(db_url: str) -> Engine:
    return create_engine(db_url, pool_size=5, max_overflow=10, pool_pre_ping=True)


def get_engine() -> Engine:
    return _build_engine(get_settings().database_url)


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
