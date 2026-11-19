"""Data Fusion: junta a nota da IA e a do contexto numa confiabilidade só."""

from decimal import ROUND_HALF_UP, Decimal

from data_fusion.models import (
    ComponenteConfiabilidade,
    EventoFusionInput,
    ResultadoFusao,
)
from data_fusion.scores import pontuar_contexto, pontuar_ia

# Pesos fixos das duas dimensões: IA com 4/7 (57%) e contexto com 3/7 (43%).
# O aviso do INMET entra como parte do contexto. Os pesos só mudam quando uma
# dimensão não tem nota, e aí a outra fica com 100%.
PESOS = {
    "ia": 4 / 7,
    "contexto": 3 / 7,
}


def _nivel_confiabilidade(valor: float) -> str:
    # Usa o valor arredondado que aparece na tela, igual à promoção para ativo.
    # Assim 79,77% aparece como 80% e já conta como alta.
    exibido = Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if exibido >= Decimal("0.80"):
        return "alta"
    if exibido >= Decimal("0.55"):
        return "media"
    return "baixa"


def calcular_confiabilidade(entrada: EventoFusionInput) -> ResultadoFusao:
    dimensoes = [
        ("ia", pontuar_ia(entrada.evidencias_ia)),
        ("contexto", pontuar_contexto(entrada.tipo, entrada.dados_contexto)),
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
                peso_base=round(PESOS[chave], 4),
            )
        )

    confiabilidade = round(min(1.0, max(0.0, total)), 4)

    return ResultadoFusao(
        evento_id=entrada.evento_id,
        confiabilidade=confiabilidade,
        nivel=_nivel_confiabilidade(confiabilidade),
        componentes=componentes,
    )
