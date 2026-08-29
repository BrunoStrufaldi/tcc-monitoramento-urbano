"""Prior espacial de alagamento: "essa via costuma alagar?".

Camada de referência ESTÁTICA — não é gatilho de detecção nem fonte ao vivo. O
grupo removeu o GeoSampa/Defesa Civil enquanto *fonte em lote que disparava
evento* (dado defasado, carimbado com hora errada). Aqui o histórico entra só
como prior: quando o modelo de incidentes suspeita de alagamento numa câmera, a
fusão consulta se aquele trecho tem histórico de alagar e usa isso para
calibrar a confiabilidade — reforça quando já há chuva/aviso ao vivo e derruba
quando não há nenhum sinal e a via nunca alagou (falso positivo provável).

Dados em ``data/pontos_alagamento_sp.json`` — pontos recorrentes no entorno das
11 câmeras CET-SP (``cet_camera_catalog``), compilados do histórico do CGE-SP e
da camada de Desastres do GeoSampa. Coordenadas aproximadas em nível de
cruzamento (mesma limitação do catálogo de câmeras).
"""

from __future__ import annotations

import json
from functools import lru_cache
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path

_ARQUIVO_PONTOS = Path(__file__).resolve().parent / "data" / "pontos_alagamento_sp.json"

# Índice base 0-10 por frequência histórica, antes do ajuste por distância.
_INDICE_POR_RECORRENCIA = {
    "cronico": 9.0,
    "frequente": 6.0,
    "ocasional": 3.0,
}


@lru_cache(maxsize=1)
def _carregar_pontos() -> tuple[dict, ...]:
    with open(_ARQUIVO_PONTOS, encoding="utf-8") as arquivo:
        return tuple(json.load(arquivo)["pontos"])


def _distancia_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância aproximada em linha reta (haversine), em metros."""
    r = 6_371_000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return r * 2 * atan2(sqrt(a), sqrt(1 - a))


def indice_historico(
    latitude: float,
    longitude: float,
    raio_total_m: float = 400.0,
    raio_pleno_m: float = 150.0,
) -> tuple[float, str]:
    """``(indice 0-10, descrição)`` do ponto de alagamento conhecido mais
    relevante em torno da coordenada.

    Peso pleno até ``raio_pleno_m``; decai linearmente até zero em
    ``raio_total_m``. Retorna ``(0.0, ...)`` quando não há nenhum ponto
    conhecido dentro do raio — o motor de fusão trata isso como "via sem
    histórico" (diferente de ausência da chave, que significa "sem informação").
    """
    melhor_indice = 0.0
    melhor_descricao = "via sem histórico de alagamento conhecido nas proximidades"

    for ponto in _carregar_pontos():
        distancia = _distancia_m(latitude, longitude, ponto["latitude"], ponto["longitude"])
        if distancia > raio_total_m:
            continue

        base = _INDICE_POR_RECORRENCIA.get(ponto["recorrencia"], 0.0)
        if distancia <= raio_pleno_m:
            fator = 1.0
        else:
            fator = (raio_total_m - distancia) / (raio_total_m - raio_pleno_m)

        indice = round(base * fator, 1)
        if indice > melhor_indice:
            melhor_indice = indice
            melhor_descricao = (
                f"{ponto['logradouro']} (~{int(distancia)} m, recorrência {ponto['recorrencia']})"
            )

    return melhor_indice, melhor_descricao
