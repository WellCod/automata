"""Download de URL para ingestão, com a checagem de SSRF dos servidores MCP (ADR-0010).

Os redirects são seguidos à mão para checar cada salto: seguidos pelo cliente HTTP,
um 302 levaria a requisição para a rede interna sem passar pela checagem.
"""

from dataclasses import dataclass
from urllib.parse import urljoin

from app.mcp.egress import check_url, guarded_client

MAX_REDIRECTS = 3
TIMEOUT_SECONDS = 20.0


class FetchFailed(ValueError):
    pass


@dataclass
class Fetched:
    url: str
    content_type: str
    data: bytes


def fetch_url(url: str, max_bytes: int) -> Fetched:
    current = url
    with guarded_client(timeout=TIMEOUT_SECONDS) as client:
        for _ in range(MAX_REDIRECTS + 1):
            check_url(current)
            with client.stream("GET", current, headers={"User-Agent": "automata-rag/1"}) as resp:
                if resp.is_redirect:
                    location = resp.headers.get("location")
                    if not location:
                        raise FetchFailed("redirect sem destino")
                    current = urljoin(current, location)
                    continue
                if resp.status_code >= 400:
                    raise FetchFailed(f"{current} respondeu {resp.status_code}")
                chunks: list[bytes] = []
                size = 0
                for chunk in resp.iter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise FetchFailed(f"conteúdo maior que {max_bytes // (1024 * 1024)} MB")
                    chunks.append(chunk)
                content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                return Fetched(url=current, content_type=content_type, data=b"".join(chunks))
    raise FetchFailed(f"mais de {MAX_REDIRECTS} redirects")
