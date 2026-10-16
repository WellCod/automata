"""Leitura de headers de proxy (X-Forwarded-*) só quando o peer é confiável."""

from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network

from starlette.requests import Request

from app.settings import get_settings

Networks = list[IPv4Network | IPv6Network]


def trusted_networks() -> Networks:
    return [
        ip_network(p.strip(), strict=False)
        for p in get_settings().trusted_proxies.split(",")
        if p.strip()
    ]


def is_trusted(ip: str, networks: Networks) -> bool:
    try:
        addr = ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in networks)


def _peer(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def get_client_ip(request: Request) -> str:
    """IP do cliente, honrando X-Forwarded-For só quando vem de proxy confiável.

    Percorre o header da direita para a esquerda e devolve o primeiro hop que
    não é proxy confiável: os valores à esquerda dele são do cliente e podem
    ser forjados.
    """
    peer = _peer(request)
    networks = trusted_networks()
    if not is_trusted(peer, networks):
        return peer
    hops = [h.strip() for h in request.headers.get("X-Forwarded-For", "").split(",") if h.strip()]
    for hop in reversed(hops):
        if not is_trusted(hop, networks):
            return hop
    return peer


def is_https(request: Request) -> bool:
    """Se o cliente chegou por HTTPS, inclusive com TLS terminado num proxy confiável."""
    if request.url.scheme == "https":
        return True
    if not is_trusted(_peer(request), trusted_networks()):
        return False
    proto = request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip().lower()
    return proto == "https"
