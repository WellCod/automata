"""Modelos além da matriz fixa, pelo ambiente (ARQ-02).

Modelo recém-lançado, Azure OpenAI ou outro endpoint compatível com a API da OpenAI
entram sem release:

    EXTRA_MODELS='[{"id": "gpt-4.1", "provider": "openai", "structured_output": true,
                    "input_price": 2, "output_price": 8},
                   {"id": "azure-gpt-4o", "provider": "openai", "model": "gpt-4o",
                    "base_url": "https://empresa.openai.azure.com/openai/v1",
                    "api_key_env": "AZURE_OPENAI_KEY", "vision": true}]'

`id` é o nome que aparece no painel; `model`, o que vai ao provedor (padrão: o próprio
`id`). JSON inválido não derruba a API: vale a matriz fixa e fica o aviso no log.
"""

import json
import logging
import os
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

logger = logging.getLogger(__name__)


class ExtraModel(BaseModel):
    """Um item do EXTRA_MODELS: provedor, endpoint, chave, capabilities e preço."""

    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:/-]+$")
    provider: Literal["anthropic", "openai"]
    model: str | None = Field(default=None, max_length=128)
    base_url: str | None = Field(default=None, max_length=500)
    # nome da variável com a chave; vazio usa ANTHROPIC_API_KEY ou OPENAI_API_KEY
    api_key_env: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]*$")
    extended_thinking: bool = False
    structured_output: bool = False
    vision: bool = False
    # dólar por milhão de tokens; sem preço o custo do run fica vazio
    input_price: float | None = Field(default=None, ge=0)
    output_price: float | None = Field(default=None, ge=0)

    @property
    def key_env(self) -> str:
        """Variável de ambiente com a chave do provedor."""
        default = "ANTHROPIC_API_KEY" if self.provider == "anthropic" else "OPENAI_API_KEY"
        return self.api_key_env or default


# cache pelo texto da variável: o EXTRA_MODELS é lido a cada request, e um valor novo
# (nos testes, por exemplo) gera outra entrada em vez de reaproveitar a antiga
@lru_cache(maxsize=4)
def _parse(raw: str) -> dict[str, ExtraModel]:
    """Modelos do JSON pelo id; JSON inválido vira vazio com aviso no log."""
    if not raw.strip():
        return {}
    try:
        models = TypeAdapter(list[ExtraModel]).validate_python(json.loads(raw))
    except (ValueError, ValidationError) as exc:
        logger.warning("EXTRA_MODELS inválido; só a matriz fixa", extra={"error": str(exc)})
        return {}
    return {model.id: model for model in models}


def extra_models() -> dict[str, ExtraModel]:
    """Modelos do EXTRA_MODELS pelo id, lidos do ambiente a cada chamada."""
    return _parse(os.environ.get("EXTRA_MODELS", ""))
