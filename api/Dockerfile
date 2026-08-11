FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.2 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim AS runner

RUN useradd --create-home --shell /bin/bash app

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini alembic.ini
COPY scripts/ scripts/
COPY entrypoint.sh entrypoint.sh

RUN chmod +x entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"

USER app

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
