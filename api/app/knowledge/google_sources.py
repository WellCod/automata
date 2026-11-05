"""Google Drive e Cloud Storage como origem de uma base (ADR-0039).

Conta de serviço: JWT RS256 assinado com a chave do JSON e trocado por um token no
`token_uri` (grant jwt-bearer), sem a biblioteca do Google. Só leitura.
"""

import json
import time
from collections.abc import Iterator
from typing import Any
from urllib.parse import quote

import httpx
import jwt

from app.knowledge.sources import (
    MAX_DEPTH,
    SUPPORTED,
    TIMEOUT_S,
    RemoteFile,
    SourceError,
    _inside,
    _raise_for,
)
from app.mcp.egress import guarded_client
from app.schemas.knowledge_connector import GCSSettings, GDriveSettings

DRIVE = "https://www.googleapis.com/drive/v3"
STORAGE = "https://storage.googleapis.com/storage/v1"
TOKEN_URI = "https://oauth2.googleapis.com/token"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
STORAGE_SCOPE = "https://www.googleapis.com/auth/devstorage.read_only"
FOLDER = "application/vnd.google-apps.folder"
# arquivos nativos do Google viram texto pelo export do Drive
EXPORTS: dict[str, tuple[str, str]] = {
    "application/vnd.google-apps.document": ("text/plain", "txt"),
    "application/vnd.google-apps.spreadsheet": ("text/csv", "csv"),
    "application/vnd.google-apps.presentation": ("text/plain", "txt"),
}


class ServiceAccount:
    """Token de acesso a partir do JSON da conta de serviço, guardado até perto de vencer."""

    def __init__(self, raw: str, scope: str, http: httpx.Client) -> None:
        try:
            info = json.loads(raw)
            self.email = str(info["client_email"])
            self._key = str(info["private_key"])
            self._kid = str(info.get("private_key_id") or "")
        except (ValueError, KeyError, TypeError) as exc:
            raise SourceError("JSON da conta de serviço inválido") from exc
        # o token_uri do JSON não é seguido: um JSON adulterado mandaria a assinatura a outro host
        self._scope = scope
        self._http = http
        self._token: str | None = None
        self._expires = 0.0

    def headers(self) -> dict[str, str]:
        if self._token is None or time.time() > self._expires - 60:
            now = int(time.time())
            claims = {
                "iss": self.email,
                "scope": self._scope,
                "aud": TOKEN_URI,
                "iat": now,
                "exp": now + 3600,
            }
            try:
                assertion = jwt.encode(
                    claims, self._key, algorithm="RS256", headers={"kid": self._kid}
                )
            except Exception as exc:
                raise SourceError("chave privada da conta de serviço inválida") from exc
            resp = self._http.post(
                TOKEN_URI,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
            )
            _raise_for(resp, "Google (login da conta de serviço)")
            body = resp.json()
            self._token = str(body["access_token"])
            self._expires = time.time() + int(body.get("expires_in") or 3600)
        return {"Authorization": f"Bearer {self._token}"}


def _account(secret: dict[str, str], scope: str, http: httpx.Client) -> ServiceAccount:
    raw = secret.get("service_account_json", "")
    if not raw.strip():
        raise SourceError("o conector do Google precisa do JSON da conta de serviço")
    return ServiceAccount(raw, scope, http)


class GDriveSource:
    def __init__(
        self, settings: GDriveSettings, secret: dict[str, str], client: httpx.Client | None = None
    ) -> None:
        self.settings = settings
        self.label = f"gdrive:{settings.folder_id}"
        self.truncated = False
        self._http = client or guarded_client(timeout=TIMEOUT_S)
        self._auth = _account(secret, DRIVE_SCOPE, self._http)

    def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        resp = self._http.get(url, params=params, headers=self._auth.headers())
        _raise_for(resp, "Google Drive")
        return resp

    def _children(self, folder: str) -> Iterator[dict[str, Any]]:
        params: dict[str, Any] = {
            "q": f"'{folder}' in parents and trashed=false",
            "fields": "nextPageToken,files(id,name,mimeType,md5Checksum,modifiedTime,size)",
            "pageSize": 1000,
        }
        if self.settings.shared_drive:
            params |= {"supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
        while True:
            page = self._get(f"{DRIVE}/files", params).json()
            yield from page.get("files", [])
            token = page.get("nextPageToken")
            if not token:
                return
            params["pageToken"] = token

    def list_files(self) -> list[RemoteFile]:
        files: list[RemoteFile] = []

        def walk(folder: str, relative: str, depth: int) -> None:
            for item in self._children(folder):
                name = str(item["name"])
                path = f"{relative}/{name}" if relative else name
                mime = str(item.get("mimeType") or "")
                if mime == FOLDER:
                    if depth < MAX_DEPTH:
                        walk(str(item["id"]), path, depth + 1)
                    continue
                if mime in EXPORTS:
                    # o nativo não tem md5: a versão é a data da última edição
                    path = f"{path}.{EXPORTS[mime][1]}"
                    version = str(item.get("modifiedTime") or "")
                else:
                    version = str(item.get("md5Checksum") or item.get("modifiedTime") or "")
                files.append(
                    RemoteFile(
                        path=path,
                        version=version,
                        size=int(item.get("size") or 0),
                        ref=f"{item['id']}|{mime}",
                    )
                )

        walk(self.settings.folder_id, "", 0)
        return [f for f in files if f.extension in SUPPORTED]

    def download(self, file: RemoteFile) -> bytes:
        file_id, _, mime = file.ref.partition("|")
        if mime in EXPORTS:
            url = f"{DRIVE}/files/{quote(file_id, safe='')}/export"
            return self._get(url, {"mimeType": EXPORTS[mime][0]}).content
        params: dict[str, Any] = {"alt": "media"}
        if self.settings.shared_drive:
            params["supportsAllDrives"] = "true"
        return self._get(f"{DRIVE}/files/{quote(file_id, safe='')}", params).content


class GCSSource:
    def __init__(
        self, settings: GCSSettings, secret: dict[str, str], client: httpx.Client | None = None
    ) -> None:
        self.settings = settings
        self.label = f"gcs:{settings.bucket}"
        self.truncated = False
        self._http = client or guarded_client(timeout=TIMEOUT_S)
        self._auth = _account(secret, STORAGE_SCOPE, self._http)

    def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        resp = self._http.get(url, params=params, headers=self._auth.headers())
        _raise_for(resp, f"Cloud Storage {self.settings.bucket}")
        return resp

    def list_files(self) -> list[RemoteFile]:
        prefix = self.settings.prefix.strip("/")
        params: dict[str, Any] = {"prefix": f"{prefix}/" if prefix else "", "maxResults": 1000}
        bucket = quote(self.settings.bucket, safe="")
        files: list[RemoteFile] = []
        while True:
            page = self._get(f"{STORAGE}/b/{bucket}/o", params).json()
            for obj in page.get("items", []):
                key = str(obj["name"])
                relative = _inside(key, prefix)
                if relative is None or key.endswith("/"):
                    continue
                files.append(
                    RemoteFile(
                        path=relative,
                        version=str(obj.get("generation") or obj.get("md5Hash") or ""),
                        size=int(obj.get("size") or 0),
                        ref=key,
                    )
                )
            token = page.get("nextPageToken")
            if not token:
                return files
            params["pageToken"] = token

    def download(self, file: RemoteFile) -> bytes:
        bucket = quote(self.settings.bucket, safe="")
        url = f"{STORAGE}/b/{bucket}/o/{quote(file.ref, safe='')}"
        return self._get(url, {"alt": "media"}).content
