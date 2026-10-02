from dataclasses import dataclass, field


@dataclass
class EvidenciaIA:
    confianca: float | None = None
    modelo_ia: str | None = None
    classe_detectada: str | None = None


@dataclass
class DadoContexto:
    """Sinal independente da câmera: chuva (Open-Meteo), aviso INMET, histórico
    de alagamento da via, índice de veículos do frame ou TomTom."""

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
    # Peso antes do rateio entre as dimensões presentes (o de contexto já com
    # o ajuste de concordância); `peso` é o efetivamente aplicado.
    peso_base: float = 0.0


@dataclass
class ResultadoFusao:
    evento_id: int
    confiabilidade: float
    nivel: str
    componentes: list[ComponenteConfiabilidade]
