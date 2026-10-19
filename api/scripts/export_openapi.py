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

from app.routers import PROTECTED_ROUTERS  # noqa: E402
from app.routers.auth import router as auth_router  # noqa: E402

# um schema só por modelo: os recursivos do workflow geravam ConfigPayload-Input e -Output
app = FastAPI(title="automata", version="0.1.0", separate_input_output_schemas=False)
for router in [*PROTECTED_ROUTERS, auth_router]:
    app.include_router(router)

print(json.dumps(app.openapi()))
