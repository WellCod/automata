#!/bin/sh
set -e
alembic upgrade head
python -m app.agno_migrations
exec "$@"
