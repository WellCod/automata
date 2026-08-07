"""Exporta o schema OpenAPI dos roteadores customizados para stdout.

Usado pelo pnpm gen:api no painel para gerar tipos TypeScript.
Não inicia o AgentOS nem conecta ao banco.
"""

import json
import os
import sys

# Mínimo para pydantic-settings não quebrar sem variáveis de ambiente reais
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://localhost/automata")
os.environ.setdefault("JWT_PRIVATE_KEY", "placeholder")
os.environ.setdefault("JWT_PUBLIC_KEY", "placeholder")

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI  # noqa: E402

from app.routers.linter import router as linter_router  # noqa: E402
from app.routers.models import router as models_router  # noqa: E402
from app.routers.usage import router as usage_router  # noqa: E402

app = FastAPI(title="automata", version="0.1.0")
app.include_router(models_router)
app.include_router(linter_router)
app.include_router(usage_router)

print(json.dumps(app.openapi()))
