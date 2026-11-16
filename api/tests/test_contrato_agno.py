"""Internos do Agno e do httpx que o Automata usa, conferidos a cada upgrade (ARQ-01).

Um upgrade que renomeie um destes atributos desligaria em silêncio a proteção que
depende dele: o pino de IP das saídas (SSRF), o mapa de tipos de etapa, o reranker que
levanta erro, a conexão estrita do MCP e a exclusão do titular nas tabelas do Agno.
"""

import httpx

# tabelas do Agno com user_id que a exclusão do titular não precisa varrer, e por quê
IGNORED_USER_TABLES = {
    # recursos do AgentOS que o Automata não usa ou bloqueia
    "AUTH_TOKEN_TABLE_SCHEMA",
    "SERVICE_ACCOUNT_TABLE_SCHEMA",
    "COMPONENT_TABLE_SCHEMA",
    "KNOWLEDGE_TABLE_SCHEMA",
    "PRODUCTS_TABLE_SCHEMA",
    "PROJECTS_TABLE_SCHEMA",
    "SOURCES_TABLE_SCHEMA",
    "TASKS_TABLE_SCHEMA",
    "SCHEDULE_TABLE_SCHEMA",
    # saem pela sessão do titular, na ordem do delete_session
    "COMPACTIONS_TABLE_SCHEMA",
}
COVERED = {
    "SESSION_TABLE_SCHEMA": "sessions",
    "MEMORY_TABLE_SCHEMA": "memories",
    "APPROVAL_TABLE_SCHEMA": "approvals",
    "TOOL_RESULTS_TABLE_SCHEMA": "tool_results",
    "TRACE_TABLE_SCHEMA": "traces",
    "JOBS_TABLE_SCHEMA": "jobs",
    "EVAL_TABLE_SCHEMA": "eval_runs",
    "LEARNINGS_TABLE_SCHEMA": "learnings",
    "METRICS_TABLE_SCHEMA": "metrics",
}


def test_pino_de_ip_do_httpx_ainda_alcanca_o_backend() -> None:
    from app.mcp.egress import guarded_client

    client = httpx.Client()
    assert hasattr(client._transport._pool, "_network_backend")  # type: ignore[attr-defined]
    guarded = guarded_client()
    backend = guarded._transport._pool._network_backend  # type: ignore[attr-defined]
    assert type(backend).__name__ == "_PinnedBackend"


def test_internos_do_agno_usados_pelo_app() -> None:
    from agno.knowledge.reranker.cohere import CohereReranker
    from agno.tools.mcp import MCPTools
    from agno.workflow.workflow import STEP_TYPE_MAPPING

    assert isinstance(STEP_TYPE_MAPPING, dict)
    assert callable(getattr(CohereReranker, "_rerank", None))
    assert callable(getattr(MCPTools, "_connect", None))


def test_tabelas_do_agno_com_user_id_estao_no_mapa_da_exclusao() -> None:
    import agno.db.postgres.schemas as schemas

    from app.data_subjects import AGNO_BY_USER

    with_user = {
        name
        for name in dir(schemas)
        if name.endswith("_TABLE_SCHEMA") and "user_id" in getattr(schemas, name)
    }
    # tabela nova com user_id num upgrade: decidir se a exclusão a varre
    assert with_user - IGNORED_USER_TABLES == set(COVERED)
    assert set(COVERED.values()) | {"runs"} == set(AGNO_BY_USER)
    assert "user_id" in schemas._get_run_table_schema()
