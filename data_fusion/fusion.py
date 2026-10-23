"""Data Fusion: junta a nota da IA e a do contexto numa confiabilidade só."""

from data_fusion.models import (
    ComponenteConfiabilidade,
    EventoFusionInput,
    ResultadoFusao,
)
from data_fusion.scores import fator_peso_contexto, pontuar_contexto, pontuar_ia

# Pesos das duas dimensões: IA com 4/7 (57%) e contexto com 3/7 (43%).
# O aviso do INMET entra como parte do contexto.
PESOS = {
    "ia": 4 / 7,
    "contexto": 3 / 7,
}


def _nivel_confiabilidade(valor: float) -> str:
    if valor >= 0.80:
        return "alta"
    if valor >= 0.55:
        return "media"
    return "baixa"


def calcular_confiabilidade(entrada: EventoFusionInput) -> ResultadoFusao:
    contexto, detalhe_contexto = pontuar_contexto(entrada.tipo, entrada.dados_contexto)
    # O peso do contexto muda conforme as fontes concordam ou não.
    fator_contexto, nota_peso = fator_peso_contexto(entrada.tipo, entrada.dados_contexto)
    if contexto > 0 and nota_peso:
        detalhe_contexto += f" · {nota_peso}"
    pesos_base = {**PESOS, "contexto": PESOS["contexto"] * fator_contexto}

    dimensoes = [
        ("ia", pontuar_ia(entrada.evidencias_ia)),
        ("contexto", (contexto, detalhe_contexto)),
    ]

    componentes: list[ComponenteConfiabilidade] = []
    total = 0.0
    peso_disponivel = sum(pesos_base[chave] for chave, (pontuacao, _) in dimensoes if pontuacao > 0)

    for chave, (pontuacao, detalhe) in dimensoes:
        peso = (pesos_base[chave] / peso_disponivel) if pontuacao > 0 and peso_disponivel else 0.0
        contribuicao = round(pontuacao * peso, 4)
        total += contribuicao
        componentes.append(
            ComponenteConfiabilidade(
                nome=chave,
                pontuacao=round(pontuacao, 4),
                peso=round(peso, 4),
                contribuicao=contribuicao,
                detalhe=detalhe,
                peso_base=round(pesos_base[chave], 4),
            )
        )

    confiabilidade = round(min(1.0, max(0.0, total)), 4)

    return ResultadoFusao(
        evento_id=entrada.evento_id,
        confiabilidade=confiabilidade,
        nivel=_nivel_confiabilidade(confiabilidade),
        componentes=componentes,
    )
