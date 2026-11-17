FROM python:3.15-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.2 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.15-slim AS runner

RUN useradd --create-home --shell /bin/bash app

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini alembic.ini
COPY fixtures/ fixtures/
COPY scripts/ scripts/
COPY entrypoint.sh entrypoint.sh

RUN python3 -c "p=open('entrypoint.sh','rb');c=p.read();p.close();c=c.lstrip(b'\xef\xbb\xbf').replace(b'\r\n',b'\n').replace(b'\r',b'\n');p=open('entrypoint.sh','wb');p.write(c);p.close()" && chmod +x entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"
# versão publicada (tag) e revisão do git, mostradas no /health (OPS-04)
ARG AUTOMATA_VERSION=dev
ARG AUTOMATA_REVISION=
ENV AUTOMATA_VERSION=$AUTOMATA_VERSION AUTOMATA_REVISION=$AUTOMATA_REVISION

USER app

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
