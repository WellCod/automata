from dataclasses import asdict

from fastapi import APIRouter

from app.agents.capabilities import all_capabilities

router = APIRouter(prefix="/api/v1/models", tags=["models"])


@router.get("/capabilities")
def list_capabilities() -> dict[str, dict[str, bool]]:
    return {model_id: asdict(caps) for model_id, caps in all_capabilities().items()}
