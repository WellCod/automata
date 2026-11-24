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
    """Baixa a URL conferindo cada redirect e cortando o download acima de `max_bytes`."""
    current_url = url
    with guarded_client(timeout=TIMEOUT_SECONDS) as client:
        for _ in range(MAX_REDIRECTS + 1):
            check_url(current_url)
            with client.stream(
                "GET", current_url, headers={"User-Agent": "automata-rag/1"}
            ) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise FetchFailed("redirect sem destino")
                    current_url = urljoin(current_url, location)
                    continue
                if response.status_code >= 400:
                    raise FetchFailed(f"{current_url} respondeu {response.status_code}")
                # lido em pedaços para parar no teto sem trazer o corpo inteiro para a memória
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise FetchFailed(f"conteúdo maior que {max_bytes // (1024 * 1024)} MB")
                    chunks.append(chunk)
                content_type = (
                    response.headers.get("content-type", "").split(";")[0].strip().lower()
                )
                return Fetched(url=current_url, content_type=content_type, data=b"".join(chunks))
    raise FetchFailed(f"mais de {MAX_REDIRECTS} redirects")
