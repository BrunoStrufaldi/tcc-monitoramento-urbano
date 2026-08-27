"""Primitivas locais de autenticação; nenhum segredo é definido no código."""

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.auditoria_acao import AuditoriaAcao
from app.models.usuario import Usuario

_PASSWORD_ITERATIONS = 600_000
_bearer = HTTPBearer(auto_error=False)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PASSWORD_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(_PASSWORD_ITERATIONS, _b64encode(salt), _b64encode(derived))


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, encoded_salt, encoded_hash = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        expected = _b64decode(encoded_hash)
        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), _b64decode(encoded_salt), int(iterations))
        return hmac.compare_digest(derived, expected)
    except (ValueError, TypeError):
        return False


def _secret() -> bytes:
    if not settings.auth_secret_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AUTH_SECRET_KEY não configurada")
    return settings.auth_secret_key.encode("utf-8")


def create_access_token(usuario: Usuario) -> tuple[str, int]:
    expires_in = settings.auth_token_expire_minutes * 60
    payload = {"sub": str(usuario.id), "perfil": usuario.perfil, "exp": int((datetime.now(UTC) + timedelta(seconds=expires_in)).timestamp())}
    encoded = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64encode(hmac.new(_secret(), encoded.encode("ascii"), hashlib.sha256).digest())
    return encoded + "." + signature, expires_in


def decode_access_token(token: str) -> dict[str, object]:
    try:
        encoded, signature = token.split(".", 1)
        expected = _b64encode(hmac.new(_secret(), encoded.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("assinatura inválida")
        payload = json.loads(_b64decode(encoded))
        if not isinstance(payload.get("exp"), int) or payload["exp"] <= int(datetime.now(UTC).timestamp()):
            raise ValueError("token expirado")
        return payload
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado", headers={"WWW-Authenticate": "Bearer"})


def record_audit(db: Session, *, usuario_id: int | None, acao: str, evento_id: int | None, resultado: str, detalhes: dict | None = None) -> None:
    db.add(AuditoriaAcao(usuario_id=usuario_id, acao=acao, evento_id=evento_id, resultado=resultado, detalhes=detalhes))
    db.commit()


ACESSO_LIVRE_USERNAME = "acesso-livre"


def acesso_livre_user(db: Session) -> Usuario:
    """Sistema sem tela de login: qualquer requisição sem token opera como este
    usuário. Reaproveita um administrador já existente ou cria um dedicado."""
    user = (
        db.query(Usuario)
        .filter(Usuario.ativo.is_(True), Usuario.perfil == "administrador")
        .order_by(Usuario.id)
        .first()
    )
    if user is None:
        user = db.query(Usuario).filter(Usuario.ativo.is_(True)).order_by(Usuario.id).first()
    if user is None:
        user = Usuario(nome_usuario=ACESSO_LIVRE_USERNAME, senha_hash="!sem-login", perfil="administrador")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Session = Depends(get_db),
) -> Usuario:
    if credentials is None:
        user = acesso_livre_user(db)
        request.state.current_user = user
        return user
    payload = decode_access_token(credentials.credentials)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido", headers={"WWW-Authenticate": "Bearer"})
    user = db.get(Usuario, user_id)
    if not user or not user.ativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não autorizado", headers={"WWW-Authenticate": "Bearer"})
    request.state.current_user = user
    return user


def require_roles(*perfis: str) -> Callable:
    def dependency(request: Request, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)) -> Usuario:
        if user.perfil not in perfis:
            event_id = request.path_params.get("evento_id")
            record_audit(db, usuario_id=user.id, acao=request.method + " " + request.url.path, evento_id=int(event_id) if event_id and event_id.isdigit() else None, resultado="negado")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Perfil sem permissão para esta operação")
        return user
    return dependency


require_operator = require_roles("operador", "administrador")
require_admin = require_roles("administrador")


def ensure_bootstrap_admin(db: Session) -> None:
    username = settings.auth_bootstrap_admin_username
    password = settings.auth_bootstrap_admin_password
    if not username and not password:
        return
    if not username or not password:
        raise RuntimeError("Configure AUTH_BOOTSTRAP_ADMIN_USERNAME e AUTH_BOOTSTRAP_ADMIN_PASSWORD juntos")
    if db.query(Usuario).filter(Usuario.nome_usuario == username).first():
        return
    db.add(Usuario(nome_usuario=username, senha_hash=hash_password(password), perfil="administrador"))
    db.commit()
