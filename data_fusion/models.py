from dataclasses import dataclass, field


@dataclass
class EvidenciaIA:
    confianca: float | None = None
    modelo_ia: str | None = None
    classe_detectada: str | None = None


@dataclass
class DadoContexto:
    """Dado de contexto do evento, como chuva, aviso do INMET ou trânsito da TomTom."""

    chave: str
    valor_numerico: float | None = None
    unidade: str | None = None


@dataclass
class EventoFusionInput:
    evento_id: int
    tipo: str
    evidencias_ia: list[EvidenciaIA] = field(default_factory=list)
    dados_contexto: list[DadoContexto] = field(default_factory=list)


@dataclass
class ComponenteConfiabilidade:
    nome: str
    pontuacao: float
    peso: float
    contribuicao: float
    detalhe: str
    # Peso padrão da dimensão. O campo peso é o valor que realmente entrou na conta.
    peso_base: float = 0.0


@dataclass
class ResultadoFusao:
    evento_id: int
    confiabilidade: float
    nivel: str
    componentes: list[ComponenteConfiabilidade]
