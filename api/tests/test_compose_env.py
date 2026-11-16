"""O compose de produção entrega o .env inteiro à API (Fase 51, OPS-02).

Antes as variáveis eram listadas uma a uma e cerca de 25 (SSO, OTLP, preços, retenção)
nunca chegavam ao container, sem erro nenhum.
"""

import re
from pathlib import Path

import pytest
import yaml

from app.settings import Settings

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("arquivo", ["docker-compose.yml", "docker-compose.demo.yml"])
def test_api_le_o_env_inteiro(arquivo: str) -> None:
    compose = yaml.safe_load((ROOT / arquivo).read_text(encoding="utf-8"))
    env_file = compose["services"]["api"]["env_file"]
    assert [e["path"] for e in env_file] == [".env"]


def test_toda_variavel_da_api_esta_no_env_example() -> None:
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    documented = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", example, re.M))
    fields = {(f.alias or name).upper() for name, f in Settings.model_fields.items()}
    assert fields - documented == set()


def test_servicos_com_log_limitado_e_painel_local() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    for name, service in compose["services"].items():
        if "extends" in service:
            continue
        assert service["logging"]["options"]["max-size"], name
    assert compose["services"]["web"]["ports"] == ["${WEB_BIND:-127.0.0.1}:3000:3000"]
