dev:
    docker compose -f docker-compose.yml -f docker-compose.dev.yml up

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

seed set="minimal":
    docker exec \
      -e SEED_OWNER_EMAIL="${SEED_OWNER_EMAIL}" \
      -e SEED_OWNER_PASSWORD="${SEED_OWNER_PASSWORD}" \
      automata-api-1 python scripts/seed.py {{set}}
