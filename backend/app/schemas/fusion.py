from pydantic import BaseModel, Field


class ComponenteConfiabilidadeResponse(BaseModel):
    nome: str
    pontuacao: float = Field(..., ge=0, le=1)
    peso: float = Field(..., ge=0, le=1)
    contribuicao: float = Field(..., ge=0, le=1)
    detalhe: str


class ConfiabilidadeResponse(BaseModel):
    evento_id: int
    confiabilidade: float = Field(..., ge=0, le=1, description="Score fusionado (0 a 1)")
    nivel: str = Field(..., description="baixa | media | alta")
    componentes: list[ComponenteConfiabilidadeResponse]
    confianca_registrada: float | None = Field(
        None, description="Valor atual em eventos.confianca no banco"
    )
    persistido: bool = False
