"""Login por SSO via OIDC (ADR-0042): authorization code com PKCE, sem SDK de fornecedor.

Discovery, troca do código e chaves saem pelo `guarded_client`: o provedor é
configurado no ambiente, mas a API não segue redirect nem conecta em endereço interno.
"""

import base64
import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.mcp.egress import guarded_client
from app.models.oidc_login import OidcLogin
from app.models.user import UserRole
from app.settings import get_settings

STATE_TTL = timedelta(minutes=10)
CACHE_S = 3600
TIMEOUT_S = 10.0
LEEWAY_S = 60
# nunca none nem HS*: com HS*, o segredo do cliente assinaria um id_token forjado
ALGORITHMS = ("RS256", "RS384", "RS512", "PS256", "ES256", "ES384")
_RANK = {UserRole.viewer: 0, UserRole.editor: 1, UserRole.owner: 2}


class OidcError(ValueError):
    """Falha no login por SSO; a mensagem vai para quem tentou entrar."""


@dataclass(frozen=True)
class Identity:
    subject: str
    email: str | None
    email_verified: bool
    claims: dict[str, Any]


def enabled() -> bool:
    s = get_settings()
    return bool(s.oidc_issuer and s.oidc_client_id and s.oidc_redirect_uri)


def _http() -> httpx.Client:
    return guarded_client(timeout=TIMEOUT_S)


_lock = threading.Lock()
_discovery: tuple[float, dict[str, Any]] | None = None
_jwks: tuple[float, list[dict[str, Any]]] | None = None


def reset_cache() -> None:
    global _discovery, _jwks
    with _lock:
        _discovery = None
        _jwks = None


def _get_json(url: str) -> dict[str, Any]:
    try:
        with _http() as client:
            resp = client.get(url, headers={"Accept": "application/json"})
    except (httpx.HTTPError, ValueError) as exc:
        raise OidcError("Provedor de identidade fora do ar") from exc
    if resp.status_code != 200:
        raise OidcError("Provedor de identidade fora do ar")
    data = resp.json()
    if not isinstance(data, dict):
        raise OidcError("Resposta inválida do provedor de identidade")
    return data


def _issuer() -> str:
    return get_settings().oidc_issuer.rstrip("/")


def discovery() -> dict[str, Any]:
    global _discovery
    now = time.monotonic()
    with _lock:
        cached = _discovery
    if cached and now - cached[0] < CACHE_S:
        return cached[1]
    doc = _get_json(f"{_issuer()}/.well-known/openid-configuration")
    # o documento tem de ser do próprio provedor configurado
    if str(doc.get("issuer", "")).rstrip("/") != _issuer():
        raise OidcError("Discovery com issuer diferente do configurado")
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if not str(doc.get(key, "")).startswith("https://"):
            raise OidcError(f"Discovery sem {key} em https")
    with _lock:
        _discovery = (now, doc)
    return doc


def _keys(force: bool = False) -> list[dict[str, Any]]:
    global _jwks
    now = time.monotonic()
    with _lock:
        cached = _jwks
    if cached and not force and now - cached[0] < CACHE_S:
        return cached[1]
    keys = _get_json(str(discovery()["jwks_uri"])).get("keys")
    if not isinstance(keys, list):
        raise OidcError("JWKS inválido")
    with _lock:
        _jwks = (now, keys)
    return keys


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def browser_hash(browser_key: str) -> str:
    return hashlib.sha256(browser_key.encode()).hexdigest()


def start(session: Session, browser_key: str) -> str:
    """URL do provedor; state, nonce e verificador ficam na tabela por 10 minutos."""
    s = get_settings()
    doc = discovery()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    now = datetime.now(UTC)
    session.execute(delete(OidcLogin).where(OidcLogin.created_at < now - STATE_TTL))
    session.add(
        OidcLogin(
            state=state,
            nonce=nonce,
            code_verifier=verifier,
            browser_hash=browser_hash(browser_key),
        )
    )
    session.commit()
    query = {
        "response_type": "code",
        "client_id": s.oidc_client_id,
        "redirect_uri": s.oidc_redirect_uri,
        "scope": s.oidc_scopes,
        "state": state,
        "nonce": nonce,
        "code_challenge": _b64(hashlib.sha256(verifier.encode()).digest()),
        "code_challenge_method": "S256",
    }
    return f"{doc['authorization_endpoint']}?{urlencode(query)}"


def _consume(session: Session, state: str) -> OidcLogin:
    row = session.get(OidcLogin, state, with_for_update=True)
    if row is None:
        raise OidcError("Login expirado ou já usado; tente de novo")
    session.delete(row)
    session.commit()
    if row.created_at < datetime.now(UTC) - STATE_TTL:
        raise OidcError("Login expirado ou já usado; tente de novo")
    return row


def _exchange(code: str, verifier: str) -> str:
    s = get_settings()
    doc = discovery()
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": s.oidc_redirect_uri,
        "code_verifier": verifier,
    }
    methods = doc.get("token_endpoint_auth_methods_supported") or ["client_secret_basic"]
    auth: httpx.Auth | None = None
    if "client_secret_basic" in methods:
        auth = httpx.BasicAuth(s.oidc_client_id, s.oidc_client_secret)
    else:
        data["client_id"] = s.oidc_client_id
        data["client_secret"] = s.oidc_client_secret
    try:
        with _http() as client:
            resp = client.post(
                str(doc["token_endpoint"]),
                data=data,
                auth=auth if auth is not None else httpx.USE_CLIENT_DEFAULT,
                headers={"Accept": "application/json"},
            )
    except (httpx.HTTPError, ValueError) as exc:
        raise OidcError("Provedor de identidade fora do ar") from exc
    if resp.status_code != 200:
        raise OidcError("O provedor recusou o código de login")
    token = resp.json().get("id_token")
    if not isinstance(token, str):
        raise OidcError("O provedor não devolveu id_token")
    return token


def _signing_key(token: str) -> tuple[Any, str]:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        raise OidcError("id_token inválido") from exc
    alg = header.get("alg")
    if alg not in ALGORITHMS:
        raise OidcError("id_token com algoritmo não aceito")
    kid = header.get("kid")
    for force in (False, True):
        keys = _keys(force=force)
        match = [k for k in keys if kid is None or k.get("kid") == kid]
        if kid is None and len(match) != 1:
            raise OidcError("id_token sem kid e JWKS com mais de uma chave")
        if match:
            return jwt.PyJWK(match[0]).key, str(alg)
    raise OidcError("id_token assinado por chave desconhecida")


def verify(token: str, nonce: str) -> Identity:
    s = get_settings()
    key, alg = _signing_key(token)
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[alg],
            audience=s.oidc_client_id,
            issuer=str(discovery()["issuer"]),
            leeway=LEEWAY_S,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except jwt.InvalidTokenError as exc:
        raise OidcError("id_token inválido") from exc
    if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise OidcError("id_token inválido")
    # com mais de uma audiência, o azp tem de ser este cliente
    aud = claims.get("aud")
    if isinstance(aud, list) and len(aud) > 1 and claims.get("azp") != s.oidc_client_id:
        raise OidcError("id_token inválido")
    email = claims.get("email")
    verified = claims.get("email_verified") in (True, "true")
    return Identity(
        subject=str(claims["sub"]),
        email=str(email).strip().lower() if isinstance(email, str) and email else None,
        email_verified=verified,
        claims=claims,
    )


def finish(session: Session, code: str, state: str, browser_key: str) -> Identity:
    row = _consume(session, state)
    # code e state vazados não bastam: falta o segredo que só o navegador que começou tem
    if not hmac.compare_digest(row.browser_hash, browser_hash(browser_key)):
        raise OidcError("Login expirado ou já usado; tente de novo")
    return verify(_exchange(code, row.code_verifier), row.nonce)


def _claim(claims: dict[str, Any], path: str) -> Any:
    value: Any = claims
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def parse_role_map(raw: str) -> dict[str, UserRole]:
    out: dict[str, UserRole] = {}
    for item in raw.split(","):
        if "=" not in item:
            continue
        group, role = item.rsplit("=", 1)
        try:
            out[group.strip()] = UserRole(role.strip())
        except ValueError:
            continue
    return out


def role_for(identity: Identity) -> UserRole | None:
    """Maior papel entre os grupos mapeados; sem grupo mapeado, o padrão (ou nenhum)."""
    s = get_settings()
    found: list[UserRole] = []
    if s.oidc_role_claim:
        value = _claim(identity.claims, s.oidc_role_claim)
        values = value if isinstance(value, list) else [value]
        mapping = parse_role_map(s.oidc_role_map)
        found = [mapping[str(v)] for v in values if v is not None and str(v) in mapping]
    if found:
        return max(found, key=lambda r: _RANK[r])
    default = s.oidc_default_role.strip()
    return UserRole(default) if default in UserRole.__members__ else None


def domain_allowed(email: str) -> bool:
    raw = get_settings().oidc_allowed_domains
    domains = {d.strip().lower().lstrip("@") for d in raw.split(",") if d.strip()}
    return not domains or email.rsplit("@", 1)[-1] in domains


def domains_configured() -> bool:
    return bool(get_settings().oidc_allowed_domains.strip())
