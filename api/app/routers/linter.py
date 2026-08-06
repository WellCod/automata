from fastapi import APIRouter

from app.linter.prompt import LintWarning, lint_payload
from app.schemas.config import ConfigPayload

router = APIRouter(prefix="/api/v1/linter", tags=["linter"])


@router.post("", response_model=list[LintWarning])
def run_linter(payload: ConfigPayload) -> list[LintWarning]:
    return lint_payload(payload)
