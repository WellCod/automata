"""Google Drive e Cloud Storage como origem de uma base (ADR-0039), sem rede."""

import json
from typing import Any
from urllib.parse import parse_qs

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.knowledge.google_sources import (
    DRIVE_SCOPE,
    STORAGE_SCOPE,
    TOKEN_URI,
    GCSSource,
    GDriveSource,
)
from app.knowledge.sources import SourceError, source_for
from app.schemas.knowledge_connector import GCSSettings, GDriveSettings

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PEM = KEY.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode()
ACCOUNT = json.dumps(
    {
        "type": "service_account",
        "client_email": "rag@projeto.iam.gserviceaccount.com",
        "private_key": PEM,
        "private_key_id": "k1",
        # adulterado: não pode ser seguido
        "token_uri": "https://evil.example.com/token",
    }
)
SECRET = {"service_account_json": ACCOUNT}
FOLDER = "1AbCdEfGhIjKlMnOp"


class Google:
    """Responde como as APIs do Google; guarda as chamadas para conferir."""

    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes
        self.calls: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if str(request.url) == TOKEN_URI:
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        assert request.headers["authorization"] == "Bearer tok"
        for prefix, handler in self.routes.items():
            if request.url.path.startswith(prefix):
                result = handler(request)
                if isinstance(result, bytes):
                    return httpx.Response(200, content=result)
                return httpx.Response(200, json=result)
        return httpx.Response(404)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


def test_login_da_conta_de_servico_assina_para_o_google() -> None:
    google = Google({"/storage/v1/b/manuais/o": lambda r: {"items": []}})
    GCSSource(GCSSettings(bucket="manuais"), SECRET, google.client()).list_files()
    login = google.calls[0]
    assert str(login.url) == TOKEN_URI  # nunca o token_uri do JSON
    form = parse_qs(login.content.decode())
    assert form["grant_type"] == ["urn:ietf:params:oauth:grant-type:jwt-bearer"]
    claims = jwt.decode(
        form["assertion"][0], KEY.public_key(), algorithms=["RS256"], audience=TOKEN_URI
    )
    assert claims["iss"] == "rag@projeto.iam.gserviceaccount.com"
    assert claims["scope"] == STORAGE_SCOPE
    assert jwt.get_unverified_header(form["assertion"][0])["kid"] == "k1"


def test_drive_percorre_pastas_exporta_o_nativo_e_ignora_o_resto() -> None:
    tree = {
        FOLDER: [
            {
                "id": "d1",
                "name": "Política de troca",
                "mimeType": "application/vnd.google-apps.document",
                "modifiedTime": "2026-11-01T10:00:00Z",
            },
            {
                "id": "f1",
                "name": "manual.pdf",
                "mimeType": "application/pdf",
                "md5Checksum": "abc",
                "size": "2048",
            },
            {"id": "sub", "name": "planilhas", "mimeType": "application/vnd.google-apps.folder"},
            {"id": "x1", "name": "foto.png", "mimeType": "image/png", "md5Checksum": "zzz"},
        ],
        "sub": [
            {
                "id": "s1",
                "name": "Prazos",
                "mimeType": "application/vnd.google-apps.spreadsheet",
                "modifiedTime": "2026-11-02T10:00:00Z",
            },
        ],
    }

    def files(request: httpx.Request) -> Any:
        if request.url.path.endswith("/export"):
            mime = request.url.params["mimeType"]
            return f"exportado como {mime}".encode()
        if request.url.params.get("alt") == "media":
            return b"%PDF-1.4"
        parent = request.url.params["q"].split("'")[1]
        return {"files": tree[parent]}

    google = Google({"/drive/v3/files": files})
    source = GDriveSource(GDriveSettings(folder_id=FOLDER), SECRET, google.client())
    listed = {f.path: f for f in source.list_files()}
    assert set(listed) == {"Política de troca.txt", "manual.pdf", "planilhas/Prazos.csv"}
    assert listed["manual.pdf"].version == "abc"
    assert listed["Política de troca.txt"].version == "2026-11-01T10:00:00Z"
    assert source.download(listed["Política de troca.txt"]) == b"exportado como text/plain"
    assert source.download(listed["planilhas/Prazos.csv"]) == b"exportado como text/csv"
    assert source.download(listed["manual.pdf"]) == b"%PDF-1.4"
    # o token é pedido uma vez só
    assert sum(1 for c in google.calls if str(c.url) == TOKEN_URI) == 1


def test_drive_compartilhado_pede_os_parametros_do_shared_drive() -> None:
    google = Google({"/drive/v3/files": lambda r: {"files": []}})
    GDriveSource(
        GDriveSettings(folder_id=FOLDER, shared_drive=True), SECRET, google.client()
    ).list_files()
    listing = google.calls[1]
    assert listing.url.params["supportsAllDrives"] == "true"
    assert listing.url.params["includeItemsFromAllDrives"] == "true"


def test_gcs_pagina_e_usa_o_prefixo() -> None:
    pages = [
        {
            "items": [{"name": "rh/ferias.md", "generation": "1", "size": "10"}],
            "nextPageToken": "p2",
        },
        {
            "items": [
                {"name": "rh/", "generation": "2"},
                {"name": "rh/sub/beneficios.pdf", "generation": "3"},
            ]
        },
    ]

    def objects(request: httpx.Request) -> Any:
        if request.url.params.get("alt") == "media":
            return b"conteudo"
        return pages[1] if request.url.params.get("pageToken") == "p2" else pages[0]

    google = Google({"/storage/v1/b/manuais/o": objects})
    source = GCSSource(GCSSettings(bucket="manuais", prefix="rh"), SECRET, google.client())
    listed = source.list_files()
    assert [(f.path, f.version) for f in listed] == [
        ("ferias.md", "1"),
        ("sub/beneficios.pdf", "3"),
    ]
    assert google.calls[1].url.params["prefix"] == "rh/"
    assert source.download(listed[1]) == b"conteudo"
    # o nome vai inteiro codificado, barras incluídas, como a JSON API exige
    assert google.calls[-1].url.raw_path.startswith(
        b"/storage/v1/b/manuais/o/rh%2Fsub%2Fbeneficios.pdf"
    )


@pytest.mark.parametrize(
    "secret",
    [{}, {"service_account_json": "nao é json"}, {"service_account_json": '{"client_email": "x"}'}],
)
def test_conta_de_servico_invalida(secret: dict[str, str]) -> None:
    with pytest.raises(SourceError):
        source_for("gcs", {"bucket": "manuais"}, secret)


def test_escopo_do_drive_e_so_leitura() -> None:
    assert DRIVE_SCOPE.endswith("drive.readonly")
    assert STORAGE_SCOPE.endswith("devstorage.read_only")
