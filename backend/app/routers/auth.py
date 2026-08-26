from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.auth import CredenciaisLogin, TokenResposta, UsuarioCreate, UsuarioPublico
from app.security import create_access_token, get_current_user, hash_password, record_audit, require_admin, verify_password

router = APIRouter(prefix="/auth", tags=["autenticação"])


def _create_user(payload: UsuarioCreate, db: Session, perfil: str) -> Usuario:
    username = payload.nome_usuario.strip().lower()
    if db.query(Usuario).filter(Usuario.nome_usuario == username).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nome de usuário já existe")
    user = Usuario(nome_usuario=username, senha_hash=hash_password(payload.senha), perfil=perfil)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResposta)
def login(payload: CredenciaisLogin, db: Session = Depends(get_db)) -> TokenResposta:
    user = db.query(Usuario).filter(Usuario.nome_usuario == payload.nome_usuario.strip().lower()).first()
    if not user or not user.ativo or not verify_password(payload.senha, user.senha_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas", headers={"WWW-Authenticate": "Bearer"})
    token, expires_in = create_access_token(user)
    record_audit(db, usuario_id=user.id, acao="AUTH_LOGIN", evento_id=None, resultado="sucesso")
    return TokenResposta(access_token=token, expires_in=expires_in, usuario=user)


@router.get("/me", response_model=UsuarioPublico)
def me(user: Usuario = Depends(get_current_user)) -> Usuario:
    return user


@router.post("/registrar", response_model=UsuarioPublico, status_code=status.HTTP_201_CREATED)
def registrar(payload: CredenciaisLogin, db: Session = Depends(get_db)) -> Usuario:
    if not settings.auth_allow_self_registration:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Auto-registro desabilitado")
    return _create_user(UsuarioCreate(**payload.model_dump()), db, "operador")


@router.post("/usuarios", response_model=UsuarioPublico, status_code=status.HTTP_201_CREATED)
def criar_usuario(payload: UsuarioCreate, db: Session = Depends(get_db), admin: Usuario = Depends(require_admin)) -> Usuario:
    user = _create_user(payload, db, payload.perfil)
    record_audit(db, usuario_id=admin.id, acao="AUTH_CREATE_USER", evento_id=None, resultado="sucesso", detalhes={"usuario_criado_id": user.id, "perfil": user.perfil})
    return user
