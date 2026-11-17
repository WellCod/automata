from dataclasses import asdict

from fastapi import APIRouter, Depends, Response

from app.agents.capabilities import all_capabilities
from app.authz import Scope, require_scopes
from app.pricing import prices

router = APIRouter(
    prefix="/api/v1/models",
    tags=["models"],
    dependencies=[Depends(require_scopes(Scope.CONFIGS_READ))],
)


@router.get("/prices")
def list_prices(response: Response) -> dict[str, dict[str, float]]:
    """Dólar por milhão de tokens, com os ajustes de MODEL_PRICES (ADR-0021)."""
    response.headers["Cache-Control"] = "private, max-age=300"
    return {model_id: asdict(price) for model_id, price in prices().items()}


@router.get("/capabilities")
def list_capabilities(response: Response) -> dict[str, dict[str, bool]]:
    response.headers["Cache-Control"] = "public, max-age=86400"
    return {model_id: asdict(caps) for model_id, caps in all_capabilities().items()}


@router.get("/availability")
def list_availability() -> dict[str, bool]:
    """Modelo com a chave do provedor no ambiente (UX-03): sem ela o run falha na hora."""
    import os

    from app.agents.models_map import demo_replay, key_env_of

    return {
        model_id: demo_replay() or bool(os.environ.get(key_env_of(model_id)))
        for model_id in all_capabilities()
    }
