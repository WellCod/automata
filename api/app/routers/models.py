from dataclasses import asdict

from fastapi import APIRouter, Depends, Response

from app.agents.capabilities import all_capabilities
from app.authz import Scope, require_scopes

router = APIRouter(
    prefix="/api/v1/models",
    tags=["models"],
    dependencies=[Depends(require_scopes(Scope.CONFIGS_READ))],
)


@router.get("/capabilities")
def list_capabilities(response: Response) -> dict[str, dict[str, bool]]:
    response.headers["Cache-Control"] = "public, max-age=86400"
    return {model_id: asdict(caps) for model_id, caps in all_capabilities().items()}
