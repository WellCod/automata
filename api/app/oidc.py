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
# ordem dos papéis, para ficar com o maior quando a pessoa está em vários grupos
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
    """SSO ligado: issuer, client id e redirect configurados."""
    settings = get_settings()
    return bool(settings.oidc_issuer and settings.oidc_client_id and settings.oidc_redirect_uri)


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
    """GET de um objeto JSON no provedor; rede fora, status não 200 ou não objeto: `OidcError`."""
    try:
        with _http() as client:
            response = client.get(url, headers={"Accept": "application/json"})
    except (httpx.HTTPError, ValueError) as exc:
        raise OidcError("Provedor de identidade fora do ar") from exc
    if response.status_code != 200:
        raise OidcError("Provedor de identidade fora do ar")
    body = response.json()
    if not isinstance(body, dict):
        raise OidcError("Resposta inválida do provedor de identidade")
    return body


def _issuer() -> str:
    return get_settings().oidc_issuer.rstrip("/")


def discovery() -> dict[str, Any]:
    """Documento de discovery do provedor, em cache por CACHE_S e conferido antes de valer."""
    global _discovery
    now = time.monotonic()
    with _lock:
        cached = _discovery
    if cached and now - cached[0] < CACHE_S:
        return cached[1]
    discovery_doc = _get_json(f"{_issuer()}/.well-known/openid-configuration")
    # o documento tem de ser do próprio provedor configurado
    if str(discovery_doc.get("issuer", "")).rstrip("/") != _issuer():
        raise OidcError("Discovery com issuer diferente do configurado")
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if not str(discovery_doc.get(key, "")).startswith("https://"):
            raise OidcError(f"Discovery sem {key} em https")
    with _lock:
        _discovery = (now, discovery_doc)
    return discovery_doc


def _keys(force: bool = False) -> list[dict[str, Any]]:
    """Chaves públicas do provedor (JWKS), em cache por CACHE_S; `force` relê na hora."""
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
    """base64url sem o `=` de preenchimento, como o PKCE pede no code_challenge."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def browser_hash(browser_key: str) -> str:
    """Hash do segredo do navegador que começou o login; só o hash vai para o banco."""
    return hashlib.sha256(browser_key.encode()).hexdigest()


def start(session: Session, browser_key: str) -> str:
    """URL do provedor; state, nonce e verificador ficam na tabela por 10 minutos."""
    settings = get_settings()
    discovery_doc = discovery()
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
    # PKCE S256: o provedor recebe só o hash do verificador, que fica guardado até o retorno
    query = {
        "response_type": "code",
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "scope": settings.oidc_scopes,
        "state": state,
        "nonce": nonce,
        "code_challenge": _b64(hashlib.sha256(verifier.encode()).digest()),
        "code_challenge_method": "S256",
    }
    return f"{discovery_doc['authorization_endpoint']}?{urlencode(query)}"


def _consume(session: Session, state: str) -> OidcLogin:
    """Lê e apaga o login pendente do state: cada state vale uma vez só, mesmo vencido."""
    pending_login = session.get(OidcLogin, state, with_for_update=True)
    if pending_login is None:
        raise OidcError("Login expirado ou já usado; tente de novo")
    session.delete(pending_login)
    session.commit()
    if pending_login.created_at < datetime.now(UTC) - STATE_TTL:
        raise OidcError("Login expirado ou já usado; tente de novo")
    return pending_login


def _exchange(code: str, verifier: str) -> str:
    """Troca o código pelo id_token no token endpoint, com o verificador do PKCE."""
    settings = get_settings()
    discovery_doc = discovery()
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.oidc_redirect_uri,
        "code_verifier": verifier,
    }
    # sem a lista no discovery vale o padrão da especificação, client_secret_basic;
    # provedor que não aceita Basic recebe o segredo no corpo
    methods = discovery_doc.get("token_endpoint_auth_methods_supported") or ["client_secret_basic"]
    auth: httpx.Auth | None = None
    if "client_secret_basic" in methods:
        auth = httpx.BasicAuth(settings.oidc_client_id, settings.oidc_client_secret)
    else:
        form["client_id"] = settings.oidc_client_id
        form["client_secret"] = settings.oidc_client_secret
    try:
        with _http() as client:
            response = client.post(
                str(discovery_doc["token_endpoint"]),
                data=form,
                auth=auth if auth is not None else httpx.USE_CLIENT_DEFAULT,
                headers={"Accept": "application/json"},
            )
    except (httpx.HTTPError, ValueError) as exc:
        raise OidcError("Provedor de identidade fora do ar") from exc
    if response.status_code != 200:
        raise OidcError("O provedor recusou o código de login")
    token = response.json().get("id_token")
    if not isinstance(token, str):
        raise OidcError("O provedor não devolveu id_token")
    return token


def _signing_key(token: str) -> tuple[Any, str]:
    """Chave do JWKS que assinou o id_token e o algoritmo declarado, já filtrado por ALGORITHMS.

    Kid fora do cache relê o JWKS uma vez (chave trocada no provedor). Sem kid, só vale
    JWKS de uma chave: com várias não há como saber qual assinou.
    """
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        raise OidcError("id_token inválido") from exc
    algorithm = header.get("alg")
    if algorithm not in ALGORITHMS:
        raise OidcError("id_token com algoritmo não aceito")
    kid = header.get("kid")
    for force in (False, True):
        keys = _keys(force=force)
        candidates = [jwk for jwk in keys if kid is None or jwk.get("kid") == kid]
        if kid is None and len(candidates) != 1:
            raise OidcError("id_token sem kid e JWKS com mais de uma chave")
        if candidates:
            return jwt.PyJWK(candidates[0]).key, str(algorithm)
    raise OidcError("id_token assinado por chave desconhecida")


def verify(token: str, nonce: str) -> Identity:
    """Confere assinatura, audiência, emissor, validade, nonce e azp do id_token."""
    settings = get_settings()
    key, algorithm = _signing_key(token)
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[algorithm],
            audience=settings.oidc_client_id,
            issuer=str(discovery()["issuer"]),
            leeway=LEEWAY_S,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except jwt.InvalidTokenError as exc:
        raise OidcError("id_token inválido") from exc
    if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise OidcError("id_token inválido")
    # com mais de uma audiência, o azp tem de ser este cliente
    audience = claims.get("aud")
    if (
        isinstance(audience, list)
        and len(audience) > 1
        and claims.get("azp") != settings.oidc_client_id
    ):
        raise OidcError("id_token inválido")
    email = claims.get("email")
    # há provedor que manda o booleano como texto
    email_verified = claims.get("email_verified") in (True, "true")
    return Identity(
        subject=str(claims["sub"]),
        email=str(email).strip().lower() if isinstance(email, str) and email else None,
        email_verified=email_verified,
        claims=claims,
    )


def finish(session: Session, code: str, state: str, browser_key: str) -> Identity:
    """Fecha o login: consome o state, confere o navegador, troca o código e verifica o id_token."""
    pending_login = _consume(session, state)
    # code e state vazados não bastam: falta o segredo que só o navegador que começou tem
    if not hmac.compare_digest(pending_login.browser_hash, browser_hash(browser_key)):
        raise OidcError("Login expirado ou já usado; tente de novo")
    return verify(_exchange(code, pending_login.code_verifier), pending_login.nonce)


def _claim(claims: dict[str, Any], path: str) -> Any:
    """Claim por caminho com ponto (`realm_access.roles`); None quando o caminho não existe."""
    value: Any = claims
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def parse_role_map(raw: str) -> dict[str, UserRole]:
    """`OIDC_ROLE_MAP` (`grupo=papel,...`); item sem `=` ou com papel desconhecido fica de fora."""
    role_by_group: dict[str, UserRole] = {}
    for item in raw.split(","):
        if "=" not in item:
            continue
        # rsplit: o nome do grupo pode ter `=`, o papel não
        group, role = item.rsplit("=", 1)
        try:
            role_by_group[group.strip()] = UserRole(role.strip())
        except ValueError:
            continue
    return role_by_group


def role_for(identity: Identity) -> UserRole | None:
    """Maior papel entre os grupos mapeados; sem grupo mapeado, o padrão (ou nenhum)."""
    settings = get_settings()
    found: list[UserRole] = []
    if settings.oidc_role_claim:
        claim_value = _claim(identity.claims, settings.oidc_role_claim)
        groups = claim_value if isinstance(claim_value, list) else [claim_value]
        role_by_group = parse_role_map(settings.oidc_role_map)
        found = [
            role_by_group[str(group)]
            for group in groups
            if group is not None and str(group) in role_by_group
        ]
    if found:
        return max(found, key=lambda role: _RANK[role])
    default = settings.oidc_default_role.strip()
    return UserRole(default) if default in UserRole.__members__ else None


def domain_allowed(email: str) -> bool:
    """Se o domínio do e-mail está em `OIDC_ALLOWED_DOMAINS`; lista vazia libera qualquer um."""
    raw = get_settings().oidc_allowed_domains
    domains = {domain.strip().lower().lstrip("@") for domain in raw.split(",") if domain.strip()}
    return not domains or email.rsplit("@", 1)[-1] in domains


def domains_configured() -> bool:
    return bool(get_settings().oidc_allowed_domains.strip())
