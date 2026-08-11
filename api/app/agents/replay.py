"""Modelo de replay para modo demo — retorna fixtures sem chamar a API do provedor."""

import itertools
import json
import threading
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agno.models.base import Model
from agno.models.response import ModelResponse

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"
_COUNTERS: dict[str, Iterator[str]] = {}
_LOCK = threading.Lock()


def _load_fixture(model_id: str) -> list[str]:
    path = _FIXTURES_DIR / f"{model_id}.json"
    if not path.exists():
        path = _FIXTURES_DIR / "default.json"
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _next_response(model_id: str) -> str:
    with _LOCK:
        if model_id not in _COUNTERS:
            _COUNTERS[model_id] = itertools.cycle(_load_fixture(model_id))
        return next(_COUNTERS[model_id])


@dataclass
class ReplayModel(Model):
    """Substituto do modelo real no modo demo — retorna respostas pré-gravadas."""

    id: str = "replay"
    name: str = "Replay"
    provider: str = "Demo"

    def invoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        return ModelResponse(content=_next_response(self.id), role="assistant")

    async def ainvoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        return self.invoke()

    def invoke_stream(self, *args: Any, **kwargs: Any) -> Iterator[ModelResponse]:
        yield self.invoke()

    async def ainvoke_stream(self, *args: Any, **kwargs: Any) -> AsyncIterator[ModelResponse]:
        yield self.invoke()

    def _parse_provider_response(self, response: Any, **kwargs: Any) -> ModelResponse:
        raise NotImplementedError

    def _parse_provider_response_delta(self, response: Any) -> ModelResponse:
        raise NotImplementedError
