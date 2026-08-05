from agno.db.postgres import PostgresDb
from agno.os import AgentOS
from fastapi import FastAPI

from app.settings import get_settings


def create_app(auto_provision_dbs: bool = True) -> FastAPI:
    settings = get_settings()
    db = PostgresDb(db_url=settings.database_url)

    base = FastAPI(title="automata")

    return AgentOS(
        id="automata",
        db=db,
        base_app=base,
        auto_provision_dbs=auto_provision_dbs,
    ).get_app()


app = create_app()
