"""Listagem e download das origens remotas de uma base (ADR-0024).

Os bytes vão para a ingestão de sempre (`app/knowledge/ingest.py`). Os loaders
remotos do Agno gravam pelo `Knowledge` dele, sem o `content_id` por trecho e
sem a medição do embedder, então o download é nosso:

- GitHub pela API REST: árvore do branch e conteúdo bruto;
- SharePoint pelo Microsoft Graph, com client credentials;
- S3 com `boto3`.

URL configurável (GitHub Enterprise, endpoint de S3) passa pelo filtro de saída
dos servidores MCP a cada chamada, e nenhum cliente segue redirect sozinho.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from app.mcp.egress import check_url, guarded_client
from app.schemas.knowledge_connector import GitHubSettings, S3Settings, SharePointSettings

TIMEOUT_S = 30.0
# extensões que a ingestão lê; o resto da origem é ignorado
SUPPORTED = {"pdf", "docx", "md", "txt", "csv", "json", "html"}
GRAPH = "https://graph.microsoft.com/v1.0"
LOGIN = "https://login.microsoftonline.com"
# pastas do SharePoint visitadas a partir da configurada
MAX_DEPTH = 5


class SourceError(ValueError):
    pass


@dataclass(frozen=True)
class RemoteFile:
    # caminho relativo à pasta configurada: é a chave do conteúdo na base
    path: str
    version: str
    size: int
    # dado próprio da origem para baixar (id do item, URL assinada)
    ref: str = ""

    @property
    def extension(self) -> str:
        return PurePosixPath(self.path).suffix.lower().lstrip(".")

    @property
    def name(self) -> str:
        return PurePosixPath(self.path).stem or self.path


class Source(Protocol):
    label: str
    # a origem cortou a listagem (árvore grande demais do GitHub): pode faltar arquivo
    truncated: bool

    def list_files(self) -> list[RemoteFile]: ...

    def download(self, file: RemoteFile) -> bytes: ...


def _inside(path: str, folder: str) -> str | None:
    """Caminho relativo à pasta, ou None quando está fora dela."""
    folder = folder.strip("/")
    if not folder:
        return path
    if path == folder or not path.startswith(folder + "/"):
        return None
    return path[len(folder) + 1 :]


def _raise_for(resp: httpx.Response, what: str) -> None:
    if resp.is_redirect:
        raise SourceError(f"{what}: redirect recusado")
    if resp.status_code in (401, 403):
        raise SourceError(f"{what}: credencial recusada (HTTP {resp.status_code})")
    if resp.status_code == 404:
        raise SourceError(f"{what}: não encontrado")
    if resp.status_code >= 400:
        raise SourceError(f"{what}: HTTP {resp.status_code}")


class GitHubSource:
    def __init__(self, settings: GitHubSettings, secret: dict[str, str]) -> None:
        self.settings = settings
        self.label = f"github:{settings.repo}@{settings.branch}"
        self.truncated = False
        self._api = settings.api_url.rstrip("/")
        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "automata-rag/1",
        }
        if secret.get("token"):
            self._headers["Authorization"] = f"Bearer {secret['token']}"

    def _get(self, url: str, **headers: str) -> httpx.Response:
        check_url(url)
        with guarded_client(timeout=TIMEOUT_S) as client:
            resp = client.get(url, headers={**self._headers, **headers})
        _raise_for(resp, f"GitHub {self.settings.repo}")
        return resp

    def list_files(self) -> list[RemoteFile]:
        s = self.settings
        tree = self._get(
            f"{self._api}/repos/{s.repo}/git/trees/{quote(s.branch, safe='')}?recursive=1"
        ).json()
        files: list[RemoteFile] = []
        for item in tree.get("tree", []):
            if item.get("type") != "blob":
                continue
            relative = _inside(str(item["path"]), s.path)
            if relative is None:
                continue
            files.append(
                RemoteFile(
                    path=relative,
                    version=str(item["sha"]),
                    size=int(item.get("size") or 0),
                    ref=str(item["path"]),
                )
            )
        self.truncated = bool(tree.get("truncated"))
        return files

    def download(self, file: RemoteFile) -> bytes:
        s = self.settings
        url = (
            f"{self._api}/repos/{s.repo}/contents/{quote(file.ref)}?ref={quote(s.branch, safe='')}"
        )
        return self._get(url, Accept="application/vnd.github.raw").content


class S3Source:
    def __init__(self, settings: S3Settings, secret: dict[str, str]) -> None:
        self.settings = settings
        self.label = f"s3:{settings.bucket}"
        self.truncated = False
        self._secret = secret

    def _client(self) -> Any:
        import boto3

        if self.settings.endpoint_url:
            check_url(self.settings.endpoint_url)
        kwargs: dict[str, Any] = {
            "region_name": self.settings.region or None,
            "endpoint_url": self.settings.endpoint_url or None,
        }
        if self._secret.get("access_key_id"):
            kwargs["aws_access_key_id"] = self._secret["access_key_id"]
            kwargs["aws_secret_access_key"] = self._secret.get("secret_access_key", "")
        return boto3.client("s3", **kwargs)

    def list_files(self) -> list[RemoteFile]:
        prefix = self.settings.prefix.strip("/")
        files: list[RemoteFile] = []
        try:
            pages = self._client().get_paginator("list_objects_v2")
            for page in pages.paginate(
                Bucket=self.settings.bucket, Prefix=f"{prefix}/" if prefix else ""
            ):
                for obj in page.get("Contents", []):
                    key = str(obj["Key"])
                    relative = _inside(key, prefix)
                    if relative is None or key.endswith("/"):
                        continue
                    files.append(
                        RemoteFile(
                            path=relative,
                            version=str(obj.get("ETag", "")).strip('"'),
                            size=int(obj.get("Size") or 0),
                            ref=key,
                        )
                    )
        except SourceError:
            raise
        except Exception as exc:
            raise SourceError(f"S3 {self.settings.bucket}: {type(exc).__name__}: {exc}") from exc
        return files

    def download(self, file: RemoteFile) -> bytes:
        try:
            obj = self._client().get_object(Bucket=self.settings.bucket, Key=file.ref)
            data: bytes = obj["Body"].read()
        except Exception as exc:
            raise SourceError(f"S3 {file.ref}: {type(exc).__name__}: {exc}") from exc
        return data


class SharePointSource:
    def __init__(
        self,
        settings: SharePointSettings,
        secret: dict[str, str],
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self.label = f"sharepoint:{settings.hostname}{settings.site_path}"
        self.truncated = False
        self._secret = secret
        # injetável nos testes; em produção, sem seguir redirect
        self._http = client or guarded_client(timeout=TIMEOUT_S)
        self._token: str | None = None

    def _auth(self) -> dict[str, str]:
        if self._token is None:
            s = self.settings
            resp = self._http.post(
                f"{LOGIN}/{quote(s.tenant_id, safe='')}/oauth2/v2.0/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": s.client_id,
                    "client_secret": self._secret.get("client_secret", ""),
                    "scope": "https://graph.microsoft.com/.default",
                },
            )
            _raise_for(resp, "SharePoint (login)")
            self._token = str(resp.json()["access_token"])
        return {"Authorization": f"Bearer {self._token}"}

    def _get(self, url: str) -> dict[str, Any]:
        resp = self._http.get(url, headers=self._auth())
        _raise_for(resp, "SharePoint")
        result: dict[str, Any] = resp.json()
        return result

    def _site_id(self) -> str:
        s = self.settings
        site = self._get(f"{GRAPH}/sites/{s.hostname}:/{s.site_path.strip('/')}")
        return str(site["id"])

    def _children(self, site: str, folder: str) -> Iterator[dict[str, Any]]:
        url: str | None = (
            f"{GRAPH}/sites/{site}/drive/root:/{quote(folder)}:/children"
            if folder
            else f"{GRAPH}/sites/{site}/drive/root/children"
        )
        while url:
            page = self._get(url)
            yield from page.get("value", [])
            url = page.get("@odata.nextLink")

    def list_files(self) -> list[RemoteFile]:
        site = self._site_id()
        root = self.settings.folder_path.strip("/")
        files: list[RemoteFile] = []

        def walk(folder: str, relative: str, depth: int) -> None:
            for item in self._children(site, folder):
                name = str(item["name"])
                path = f"{relative}/{name}" if relative else name
                if "folder" in item and depth < MAX_DEPTH:
                    walk(f"{folder}/{name}" if folder else name, path, depth + 1)
                elif "file" in item:
                    files.append(
                        RemoteFile(
                            path=path,
                            version=str(item.get("eTag", "")),
                            size=int(item.get("size") or 0),
                            ref=str(item.get("@microsoft.graph.downloadUrl", "")),
                        )
                    )

        walk(root, "", 0)
        return files

    def download(self, file: RemoteFile) -> bytes:
        # URL assinada e curta do próprio Graph; sem cabeçalho de autorização
        check_url(file.ref)
        resp = self._http.get(file.ref)
        _raise_for(resp, f"SharePoint {file.path}")
        return resp.content


def source_for(kind: str, settings: dict[str, Any], secret: dict[str, str]) -> Source:
    if kind == "github":
        return GitHubSource(GitHubSettings.model_validate(settings), secret)
    if kind == "s3":
        return S3Source(S3Settings.model_validate(settings), secret)
    if kind == "sharepoint":
        return SharePointSource(SharePointSettings.model_validate(settings), secret)
    raise SourceError(f"tipo de conector desconhecido: {kind}")
