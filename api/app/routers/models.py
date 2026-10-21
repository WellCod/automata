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
