from fastapi import APIRouter, Depends

from app.authz import Scope, require_scopes
from app.linter.prompt import LintWarning, lint_payload
from app.schemas.config import ConfigPayload

router = APIRouter(
    prefix="/api/v1/linter",
    tags=["linter"],
    dependencies=[Depends(require_scopes(Scope.CONFIGS_READ))],
)


@router.post("", response_model=list[LintWarning])
def run_linter(payload: ConfigPayload) -> list[LintWarning]:
    return lint_payload(payload)
