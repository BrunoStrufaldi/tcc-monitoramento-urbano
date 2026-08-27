"""Fluxo de trânsito ao vivo via TomTom Traffic API (Flow Segment Data).

Diferente do GeoSampa (recarregado em lote — semanas a anos de defasagem;
removido do sistema por decisão do grupo de manter só dado em tempo real),
essa API responde com a velocidade média atual do trecho de via mais próximo
do ponto pedido, comparada à velocidade livre esperada — dado genuinamente ao
vivo. Cadastro self-service e gratuito em developer.tomtom.com (sem convênio
institucional, ao contrário do Waze for Cities). Requer ``TOMTOM_API_KEY``.
"""

import json
import os
from urllib.parse import urlencode
from urllib.request import urlopen

_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"


def obter_fluxo_transito(latitude: float, longitude: float) -> dict:
    """Consulta a velocidade atual x livre no trecho mais próximo do ponto."""
    api_key = os.getenv("TOMTOM_API_KEY")
    if not api_key:
        return {"disponivel": False, "fonte": "TomTom Traffic", "erro": "TOMTOM_API_KEY não configurada"}

    query = urlencode({"key": api_key, "point": f"{latitude},{longitude}", "unit": "kmph"})
    url = f"{_URL}?{query}"
    try:
        with urlopen(url, timeout=6) as response:  # nosec B310 - URL fixa, chave via query param
            payload = json.load(response)
    except Exception as exc:
        return {"disponivel": False, "fonte": "TomTom Traffic", "erro": str(exc)}

    dados = payload.get("flowSegmentData") or {}
    velocidade_atual = dados.get("currentSpeed")
    velocidade_livre = dados.get("freeFlowSpeed")
    if velocidade_atual is None or not velocidade_livre:
        return {"disponivel": False, "fonte": "TomTom Traffic", "erro": "Resposta sem dados de velocidade"}

    indice = round(max(0.0, min(10.0, 10 * (1 - velocidade_atual / velocidade_livre))), 1)
    return {
        "disponivel": True,
        "fonte": "TomTom Traffic",
        "velocidade_atual_kmh": velocidade_atual,
        "velocidade_livre_kmh": velocidade_livre,
        "indice_congestionamento": indice,
        "confianca_dado": dados.get("confidence"),
        "via_fechada": dados.get("roadClosure", False),
    }
