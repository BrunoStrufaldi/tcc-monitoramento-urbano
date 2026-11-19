from datetime import datetime

from pydantic import BaseModel, Field


class ComponenteConfiabilidadeResponse(BaseModel):
    nome: str
    pontuacao: float = Field(..., ge=0, le=1)
    peso: float = Field(..., ge=0, le=1)
    contribuicao: float = Field(..., ge=0, le=1)
    detalhe: str
    peso_base: float = Field(
        0.0, ge=0,
        description="Peso fixo da dimensão (IA 4/7, contexto 3/7), antes do rateio quando uma dimensão não tem nota",
    )


class ConfiabilidadeResponse(BaseModel):
    evento_id: int
    confiabilidade: float = Field(..., ge=0, le=1, description="Score fusionado (0 a 1)")
    nivel: str = Field(..., description="baixa | media | alta")
    componentes: list[ComponenteConfiabilidadeResponse]
    confianca_registrada: float | None = Field(
        None, description="Valor atual em eventos.confianca no banco"
    )
    persistido: bool = False
    calculado_em: datetime = Field(..., description="Horário UTC em que a fusão foi calculada")
    limiar_ativo: float = Field(
        ..., ge=0, le=1,
        description="Confiabilidade a partir da qual um evento em análise é promovido para ativo",
    )
