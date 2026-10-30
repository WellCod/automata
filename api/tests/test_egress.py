"""Saídas da API (ADR-0010, Fase 28): só endereço global e IP conferido na conexão."""

import socket
import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from app.settings import get_settings


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("JWT_PRIVATE_KEY", "x")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "x")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("ip", "internal"),
    [
        ("10.0.0.5", True),
        ("172.18.0.2", True),
        ("192.168.1.1", True),
        ("127.0.0.1", True),
        ("169.254.169.254", True),
        ("100.64.0.1", True),
        ("100.100.100.200", True),
        ("::1", True),
        ("::ffff:127.0.0.1", True),
        ("::ffff:169.254.169.254", True),
        ("fd00::1", True),
        ("0.0.0.0", True),
        ("8.8.8.8", False),
        ("2606:4700:4700::1111", False),
    ],
)
def test_so_endereco_global_passa(ip: str, internal: bool) -> None:
    from app.mcp.egress import _is_internal

    assert _is_internal(ip) is internal


class _Server:
    def __init__(self) -> None:
        self.hosts: list[str | None] = []
        seen = self.hosts

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                seen.append(self.headers.get("Host"))
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, *args: Any) -> None:
                pass

        self.http = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.http.server_address[1]
        threading.Thread(target=self.http.serve_forever, daemon=True).start()


@pytest.fixture
def server() -> Generator[_Server, None, None]:
    s = _Server()
    yield s
    s.http.shutdown()


def _fake_dns(monkeypatch: pytest.MonkeyPatch, answers: list[str]) -> None:
    """Cada consulta devolve a próxima resposta da lista (a última se repete)."""
    real = socket.getaddrinfo

    def fake(host: str, port: Any, *args: Any, **kwargs: Any) -> Any:
        if not host.endswith(".test"):
            return real(host, port, *args, **kwargs)
        ip = answers.pop(0) if len(answers) > 1 else answers[0]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    monkeypatch.setattr(socket, "getaddrinfo", fake)


def test_dns_rebinding_e_barrado_na_conexao(
    monkeypatch: pytest.MonkeyPatch, server: _Server
) -> None:
    from app.mcp.egress import EgressDenied, check_url, guarded_client

    # o check vê um IP público; a conexão, o interno
    _fake_dns(monkeypatch, ["8.8.8.8", "127.0.0.1"])
    check_url(f"https://rebind.test:{server.port}/")
    with guarded_client(timeout=5) as client, pytest.raises(EgressDenied, match="interno"):
        client.get(f"http://rebind.test:{server.port}/")
    assert server.hosts == []


def test_conexao_vai_no_ip_conferido_com_o_host_original(
    monkeypatch: pytest.MonkeyPatch, server: _Server
) -> None:
    import app.mcp.egress as egress

    # aqui o "público" é o servidor local, para ver onde o TCP abriu e qual Host chegou
    _fake_dns(monkeypatch, ["127.0.0.1"])
    monkeypatch.setattr(egress, "_is_internal", lambda ip: False)
    with egress.guarded_client(timeout=5) as client:
        resp = client.get(f"http://pinned.test:{server.port}/")
    assert resp.text == "ok"
    assert server.hosts == [f"pinned.test:{server.port}"]


def test_host_liberado_conecta_sem_conferencia(
    monkeypatch: pytest.MonkeyPatch, server: _Server
) -> None:
    from app.mcp.egress import guarded_client

    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "127.0.0.1")
    get_settings.cache_clear()
    with guarded_client(timeout=5) as client:
        assert client.get(f"http://127.0.0.1:{server.port}/").text == "ok"


def test_cliente_nao_segue_redirect_nem_usa_proxy_do_ambiente() -> None:
    from app.mcp.egress import guarded_client

    with guarded_client(timeout=5) as client:
        assert client.follow_redirects is False
        assert client._trust_env is False
