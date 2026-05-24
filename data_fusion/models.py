from dataclasses import dataclass, field


@dataclass
class EvidenciaIA:
    confianca: float | None = None
    modelo_ia: str | None = None
    classe_detectada: str | None = None


@dataclass
class DadoClima:
    chave: str
    valor_numerico: float | None = None
    unidade: str | None = None


@dataclass
class FonteInfo:
    tipo: str
    nome: str = ""
    ativo: bool = True


@dataclass
class EventoFusionInput:
    evento_id: int
    tipo: str
    evidencias_ia: list[EvidenciaIA] = field(default_factory=list)
    dados_clima: list[DadoClima] = field(default_factory=list)
    fonte: FonteInfo | None = None


@dataclass
class ComponenteConfiabilidade:
    nome: str
    pontuacao: float
    peso: float
    contribuicao: float
    detalhe: str


@dataclass
class ResultadoFusao:
    evento_id: int
    confiabilidade: float
    nivel: str
    componentes: list[ComponenteConfiabilidade]
