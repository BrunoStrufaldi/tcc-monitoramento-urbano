"""Motor de fusão: combina IA, clima e fonte oficial em um score único."""

from data_fusion.models import (
    ComponenteConfiabilidade,
    EventoFusionInput,
    ResultadoFusao,
)
from data_fusion.scores import pontuar_clima, pontuar_fonte_oficial, pontuar_ia

PESOS = {
    "ia": 0.40,
    "clima": 0.30,
    "fonte_oficial": 0.30,
}


def _nivel_confiabilidade(valor: float) -> str:
    if valor >= 0.80:
        return "alta"
    if valor >= 0.55:
        return "media"
    return "baixa"


def calcular_confiabilidade(entrada: EventoFusionInput) -> ResultadoFusao:
    dimensoes = [
        ("ia", pontuar_ia(entrada.evidencias_ia)),
        ("clima", pontuar_clima(entrada.tipo, entrada.dados_clima)),
        ("fonte_oficial", pontuar_fonte_oficial(entrada.fonte)),
    ]

    componentes: list[ComponenteConfiabilidade] = []
    total = 0.0
    peso_disponivel = sum(PESOS[chave] for chave, (pontuacao, _) in dimensoes if pontuacao > 0)

    for chave, (pontuacao, detalhe) in dimensoes:
        peso = (PESOS[chave] / peso_disponivel) if pontuacao > 0 and peso_disponivel else 0.0
        contribuicao = round(pontuacao * peso, 4)
        total += contribuicao
        componentes.append(
            ComponenteConfiabilidade(
                nome=chave,
                pontuacao=round(pontuacao, 4),
                peso=round(peso, 4),
                contribuicao=contribuicao,
                detalhe=detalhe,
            )
        )

    confiabilidade = round(min(1.0, max(0.0, total)), 4)

    return ResultadoFusao(
        evento_id=entrada.evento_id,
        confiabilidade=confiabilidade,
        nivel=_nivel_confiabilidade(confiabilidade),
        componentes=componentes,
    )
