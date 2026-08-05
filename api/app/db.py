from agno.db.postgres import PostgresDb

from app.settings import get_settings


def get_db() -> PostgresDb:
    return PostgresDb(db_url=get_settings().database_url)
