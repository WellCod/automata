"""Proteção de SSRF nas saídas da API: MCP, ingestão de URL, conectores e webhooks (ADR-0010).

A URL é configurável pelo painel e a API conecta nela: sem filtro, um
servidor apontado para a rede interna ou para o endpoint de metadados da
cloud viraria proxy para dentro da instância.

`check_url` confere na hora de salvar. Na hora de conectar, `guarded_client`
resolve o nome, confere os IPs e abre o TCP no IP conferido, com o TLS ainda
pelo nome: sem isso, um DNS de TTL zero responderia um IP público ao check e um
interno à conexão (DNS rebinding).
"""

import ipaddress
import socket
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlsplit

import httpcore
import httpx

from app.settings import get_settings


class EgressDenied(ValueError):
    pass


def _allowed_hosts() -> set[str]:
    raw = get_settings().mcp_allowed_hosts
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def _is_internal(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    # só endereço roteável na internet: fora ficam privada, loopback, link-local,
    # CGNAT (100.64.0.0/10, onde mora o metadata da Alibaba), reservada e afins
    return not addr.is_global or addr.is_multicast


def resolve_public(host: str, port: int) -> str:
    """IP público para conectar em `host`; hosts liberados voltam sem conferência."""
    host = host.lower().strip("[]")
    if host in _allowed_hosts():
        return host
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise EgressDenied(f"host {host} não resolve") from exc
    ips = [str(info[4][0]) for info in infos]
    for ip in ips:
        if _is_internal(ip):
            raise EgressDenied(f"host {host} resolve para endereço interno ({ip})")
    return ips[0]


class _PinnedBackend(httpcore.SyncBackend):
    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.NetworkStream:
        ip = resolve_public(host, port)
        return super().connect_tcp(ip, port, timeout, local_address, socket_options)


def guarded_client(**kwargs: Any) -> httpx.Client:
    """httpx.Client que confere o IP a cada conexão e não segue redirect.

    Ignora proxy das variáveis de ambiente: a conferência seria feita no proxy.
    """
    kwargs.setdefault("follow_redirects", False)
    client = httpx.Client(trust_env=False, **kwargs)
    transport = client._transport
    # o HTTPTransport do httpx 0.28 não recebe backend; o pool do httpcore 1.0 guarda
    # em _network_backend. test_egress confere que a troca vale
    transport._pool._network_backend = _PinnedBackend()  # type: ignore[attr-defined]
    return client


def check_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise EgressDenied("URL precisa ser http ou https")
    host = (parts.hostname or "").lower()
    if not host:
        raise EgressDenied("URL sem host")
    if host in _allowed_hosts():
        return
    if parts.scheme != "https":
        raise EgressDenied("http só é aceito para hosts em MCP_ALLOWED_HOSTS")
    resolve_public(host, parts.port or 443)
