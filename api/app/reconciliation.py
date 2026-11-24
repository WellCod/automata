"""Conciliação do custo estimado com o relatório de custo dos provedores (ADR-0037).

Anthropic: `GET /v1/organizations/cost_report`, chave Admin no `x-api-key`, valor em
centavos como string. OpenAI: `GET /v1/organization/costs`, chave admin no Bearer,
valor em dólares. Os dois só têm bucket diário e paginam por `has_more`/`next_page`.
O relatório é da organização inteira: só bate se a chave for exclusiva da instância.
"""

import logging
import os
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from time import monotonic
from typing import Any

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import get_engine
from app.models.embedding_usage import EmbeddingUsage
from app.models.provider_cost import ProviderCost
from app.models.usage import UsageEvent

logger = logging.getLogger(__name__)

COST_DIVERGENCE = "cost.divergence"
FETCH_EVERY_S = 3600.0
DAYS_BACK = 3
TIMEOUT_S = 20.0
_last_fetch: float | None = None

ANTHROPIC_URL = "https://api.anthropic.com/v1/organizations/cost_report"
OPENAI_URL = "https://api.openai.com/v1/organization/costs"


def provider_of(model_id: str | None) -> str | None:
    """Provedor pelo prefixo do id do modelo; None para o que fica fora da conciliação."""
    model = (model_id or "").lower()
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith(("gpt-", "o1", "o3", "o4", "text-embedding", "chatgpt")):
        return "openai"
    return None


def configured() -> dict[str, str]:
    """Chave admin de cada provedor configurado no ambiente."""
    keys = {
        "anthropic": os.environ.get("ANTHROPIC_ADMIN_KEY", ""),
        "openai": os.environ.get("OPENAI_ADMIN_KEY", ""),
    }
    return {provider: key for provider, key in keys.items() if key}


def alert_percent() -> float:
    """Diferença percentual que gera aviso; valor inválido no ambiente volta ao padrão de 20."""
    try:
        return float(os.environ.get("RECONCILIATION_ALERT_PERCENT", "20"))
    except ValueError:
        return 20.0


def _day(value: Any) -> date:
    """Dia do bucket, venha em época (OpenAI) ou em ISO 8601 (Anthropic)."""
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, UTC).date()
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


def fetch_anthropic(key: str, start: date, end: date, client: httpx.Client) -> dict[date, Decimal]:
    """Dólares por dia; o relatório traz centavos como string decimal."""
    dollars_by_day: dict[date, Decimal] = {}
    params: dict[str, Any] = {
        "starting_at": f"{start.isoformat()}T00:00:00Z",
        "ending_at": f"{end.isoformat()}T00:00:00Z",
        "bucket_width": "1d",
        "limit": 31,
    }
    headers = {"x-api-key": key, "anthropic-version": "2026-10-21", "User-Agent": "automata"}
    while True:
        response = client.get(ANTHROPIC_URL, params=params, headers=headers, timeout=TIMEOUT_S)
        response.raise_for_status()
        body = response.json()
        for bucket in body.get("data", []):
            cents = sum(
                (Decimal(str(result.get("amount") or "0")) for result in bucket.get("results", [])),
                Decimal(0),
            )
            dollars_by_day[_day(bucket["starting_at"])] = cents / Decimal(100)
        if not body.get("has_more") or not body.get("next_page"):
            return dollars_by_day
        params["page"] = body["next_page"]


def fetch_openai(key: str, start: date, end: date, client: httpx.Client) -> dict[date, Decimal]:
    """Dólares por dia; o relatório já traz `amount.value` em dólares."""
    dollars_by_day: dict[date, Decimal] = {}
    params: dict[str, Any] = {
        "start_time": int(datetime.combine(start, time(), UTC).timestamp()),
        "end_time": int(datetime.combine(end, time(), UTC).timestamp()),
        "bucket_width": "1d",
        "limit": 31,
    }
    headers = {"Authorization": f"Bearer {key}", "User-Agent": "automata"}
    while True:
        response = client.get(OPENAI_URL, params=params, headers=headers, timeout=TIMEOUT_S)
        response.raise_for_status()
        body = response.json()
        for bucket in body.get("data", []):
            total = sum(
                (
                    Decimal(str((result.get("amount") or {}).get("value") or 0))
                    for result in bucket.get("results", [])
                ),
                Decimal(0),
            )
            dollars_by_day[_day(bucket["start_time"])] = total
        if not body.get("has_more") or not body.get("next_page"):
            return dollars_by_day
        params["page"] = body["next_page"]


FETCHERS: dict[str, Callable[[str, date, date, httpx.Client], dict[date, Decimal]]] = {
    "anthropic": fetch_anthropic,
    "openai": fetch_openai,
}


def refresh(now: datetime, client: httpx.Client | None = None) -> dict[str, int]:
    """Busca os últimos dias de cada provedor configurado e grava. Nunca levanta."""
    stored: dict[str, int] = {}
    end = now.date() + timedelta(days=1)
    start = end - timedelta(days=DAYS_BACK + 1)
    http = client or httpx.Client()
    try:
        for provider, key in configured().items():
            try:
                days = FETCHERS[provider](key, start, end, http)
            except Exception as exc:
                # o detalhe pode trazer a URL; a chave nunca vai para o log
                logger.warning(
                    "relatório de custo do provedor falhou",
                    extra={"provider": provider, "error": type(exc).__name__},
                )
                continue
            with Session(get_engine()) as session:
                for day, amount in days.items():
                    session.execute(
                        insert(ProviderCost)
                        .values(provider=provider, day=day, reported_usd=amount, fetched_at=now)
                        .on_conflict_do_update(
                            index_elements=["provider", "day"],
                            set_={"reported_usd": amount, "fetched_at": now},
                        )
                    )
                session.commit()
            stored[provider] = len(days)
    finally:
        if client is None:
            http.close()
    return stored


def estimated(session: Session, start: date, end: date) -> dict[tuple[str, date], float]:
    """Custo estimado pelo Automata por provedor e dia: runs, consumo lateral e embeddings."""
    estimated_by_day: dict[tuple[str, date], float] = {}
    # filtro pelo intervalo em created_at: com date() no WHERE o índice não servia (Fase 44)
    since = datetime.combine(start, time.min, tzinfo=UTC)
    until = datetime.combine(end, time.min, tzinfo=UTC)
    day = func.date(func.timezone("UTC", UsageEvent.created_at))
    rows: list[Any] = list(
        session.execute(
            select(UsageEvent.model_id, day, func.sum(UsageEvent.cost))
            .where(UsageEvent.created_at >= since, UsageEvent.created_at < until)
            .group_by(UsageEvent.model_id, day)
        ).all()
    )
    embedding_day = func.date(func.timezone("UTC", EmbeddingUsage.created_at))
    rows += session.execute(
        select(EmbeddingUsage.model, embedding_day, func.sum(EmbeddingUsage.cost))
        .where(EmbeddingUsage.created_at >= since, EmbeddingUsage.created_at < until)
        .group_by(EmbeddingUsage.model, embedding_day)
    ).all()
    for model_id, usage_day, cost in rows:
        provider = provider_of(model_id)
        if provider is None or cost is None:
            continue
        key = (provider, usage_day)
        estimated_by_day[key] = estimated_by_day.get(key, 0.0) + float(cost)
    return estimated_by_day


def report(session: Session, days: int, today: date) -> list[dict[str, Any]]:
    """Comparação diária, por provedor, entre o custo informado e o estimado pelo Automata."""
    start = today - timedelta(days=days - 1)
    end = today + timedelta(days=1)
    reported = session.scalars(
        select(ProviderCost).where(ProviderCost.day >= start, ProviderCost.day < end)
    ).all()
    estimated_by_day = estimated(session, start, end)
    rows = []
    for item in sorted(reported, key=lambda cost_row: (cost_row.day, cost_row.provider)):
        our_estimate = estimated_by_day.get((item.provider, item.day), 0.0)
        provider_reported = float(item.reported_usd)
        difference = provider_reported - our_estimate
        rows.append(
            {
                "provider": item.provider,
                "day": item.day,
                "reported_usd": round(provider_reported, 4),
                "estimated_usd": round(our_estimate, 4),
                "diff_usd": round(difference, 4),
                "diff_percent": (
                    round(difference / provider_reported * 100, 1) if provider_reported else None
                ),
                # o dia corrente ainda recebe custo do provedor
                "closed": item.day < today,
                "fetched_at": item.fetched_at,
            }
        )
    return rows


def check_divergence(session: Session, now: datetime) -> list[tuple[str, date]]:
    """Dia fechado com diferença acima do limite gera aviso, uma vez por provedor e dia."""
    from app.alerts import broadcast, destinations_for

    global _last_fetch
    if configured() and (_last_fetch is None or monotonic() - _last_fetch >= FETCH_EVERY_S):
        _last_fetch = monotonic()
        refresh(now)
    if not destinations_for(session, COST_DIVERGENCE):
        return []
    limit = alert_percent()
    sent: list[tuple[str, date]] = []
    for row in report(session, DAYS_BACK + 1, now.date()):
        diff_percent = row["diff_percent"]
        # só dia fechado, com diferença acima do limite e ao menos US$ 1 informado
        if (
            not row["closed"]
            or diff_percent is None
            or abs(diff_percent) < limit
            or row["reported_usd"] < 1
        ):
            continue
        # alerted_at marcado por UPDATE condicional: só uma réplica manda o aviso do dia
        claimed = session.execute(
            update(ProviderCost)
            .where(
                ProviderCost.provider == row["provider"],
                ProviderCost.day == row["day"],
                ProviderCost.alerted_at.is_(None),
            )
            .values(alerted_at=now)
        )
        session.commit()
        if not getattr(claimed, "rowcount", 0):
            continue
        broadcast(
            session,
            COST_DIVERGENCE,
            {
                key: (str(value) if isinstance(value, date | datetime) else value)
                for key, value in row.items()
            },
            f"Custo de {row['provider']} em {row['day']:%d/%m}: o provedor informou "
            f"US$ {row['reported_usd']:.2f} e o Automata estimou US$ {row['estimated_usd']:.2f} "
            f"({diff_percent:+.1f}%).",
        )
        sent.append((row["provider"], row["day"]))
    return sent
