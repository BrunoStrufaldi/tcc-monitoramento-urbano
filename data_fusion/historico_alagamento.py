"""Histórico de alagamento das vias: "essa rua costuma alagar?".

Não cria alertas. Serve só para ajustar a confiabilidade quando o modelo vê
alagamento: se a via costuma alagar a nota sobe, se nunca alagou a nota desce.
Os pontos estão em data/pontos_alagamento_sp.json e foram montados a partir do
histórico do CGE-SP e do GeoSampa.
"""

from __future__ import annotations

import json
from functools import lru_cache
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path

_ARQUIVO_PONTOS = Path(__file__).resolve().parent / "data" / "pontos_alagamento_sp.json"

# Nota de 0 a 10 conforme a frequência com que o ponto alaga.
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
    """Distância aproximada em linha reta entre dois pontos, em metros."""
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
    """Nota de 0 a 10 do ponto de alagamento conhecido mais próximo.

    Quanto mais longe o ponto, menor a nota. Se não houver nenhum ponto perto,
    a nota é zero, o que quer dizer que a via não tem histórico.
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
