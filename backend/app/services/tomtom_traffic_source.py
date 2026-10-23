"""Velocidade do trânsito ao vivo pela API da TomTom.

A API compara a velocidade atual do trecho com a velocidade normal dele, o que
mostra se a via está lenta naquele momento. Precisa da TOMTOM_API_KEY.
"""

import json
from urllib.parse import urlencode
from urllib.request import urlopen

from app.config import settings

_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"


def obter_fluxo_transito(latitude: float, longitude: float) -> dict:
    """Busca a velocidade atual e a normal do trecho mais perto do ponto."""
    api_key = settings.tomtom_api_key
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
