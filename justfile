dev:
    docker compose up

test:
    cd api && uv run pytest

lint:
    cd api && uv run ruff check . && uv run ruff format --check .
    cd web && pnpm lint

migrate:
    cd api && uv run alembic upgrade head

gen-api:
    cd api && uv run python scripts/gen_openapi.py
    cd web && pnpm openapi-ts
