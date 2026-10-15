"""Proteção de SSRF para URLs de servidores MCP (ADR-0010).

A URL é configurável pelo painel e a API conecta nela: sem filtro, um
servidor apontado para a rede interna ou para o endpoint de metadados da
cloud viraria proxy para dentro da instância.
"""

import ipaddress
import socket
from urllib.parse import urlsplit

from app.settings import get_settings


class EgressDenied(ValueError):
    pass


def _allowed_hosts() -> set[str]:
    raw = get_settings().mcp_allowed_hosts
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def _is_internal(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


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
    try:
        infos = socket.getaddrinfo(host, parts.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise EgressDenied(f"host {host} não resolve") from exc
    for info in infos:
        ip = str(info[4][0])
        if _is_internal(ip):
            raise EgressDenied(f"host {host} resolve para endereço interno ({ip})")
