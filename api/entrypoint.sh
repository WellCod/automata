#!/bin/sh
set -e
# Alembic e tabelas do Agno num processo só (app/migrate.py)
python -m app.migrate
exec "$@"
