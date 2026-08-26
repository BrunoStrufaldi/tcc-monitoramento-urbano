from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PerfilUsuario = Literal["operador", "administrador"]


class CredenciaisLogin(BaseModel):
    nome_usuario: str = Field(min_length=3, max_length=64)
    senha: str = Field(min_length=12, max_length=256)


class UsuarioCreate(CredenciaisLogin):
    perfil: PerfilUsuario = "operador"


class UsuarioPublico(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome_usuario: str
    perfil: PerfilUsuario
    ativo: bool
    criado_em: datetime


class TokenResposta(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    usuario: UsuarioPublico
