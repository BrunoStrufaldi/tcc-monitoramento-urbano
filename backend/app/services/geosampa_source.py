"""Cliente WFS do GeoSampa para ocorrências oficiais da Defesa Civil e da CET.

As camadas ``risco_ocorrencia_alagamento``, ``risco_ocorrencia_queda_arvore`` e
``acidente_cet`` existem de verdade (confirmado em 2026-08-26 consultando o
serviço) e trazem coordenada real de cada ocorrência — mas são recarregadas em
lote, com defasagem de semanas a poucos meses entre o ocorrido e a publicação
(não é um feed de "aconteceu agora"). Por isso o consumidor deste módulo trata
cada registro ainda não visto como uma ocorrência a verificar via Data Fusion,
não como um evento em andamento — a confirmação depende de corroboração
adicional (clima atual no ponto, por exemplo), não só de existir o registro.

``acidente_cet`` é a camada de acidentes de trânsito levantados pela CET —
schema diferente das duas primeiras (campo de data é ``dt_acidente``, não tem
subprefeitura, mas traz contagem de feridos/óbitos e tipo do acidente).

As coordenadas vêm em SIRGAS2000 / UTM 23S (EPSG:31983) e são convertidas para
latitude/longitude (EPSG:4326, compatível com o resto do sistema).
"""

from __future__ import annotations

import httpx
from pyproj import Transformer

WFS_URL = "http://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs"

_TRANSFORMER = Transformer.from_crs("EPSG:31983", "EPSG:4326", always_xy=True)


def _buscar_camada(nome_camada: str, data_minima: str, *, timeout: float = 20.0) -> list[dict]:
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": f"geoportal:{nome_camada}",
        "outputFormat": "application/json",
        "CQL_FILTER": f"dt_ocorrencia >= '{data_minima}'",
    }
    try:
        resposta = httpx.get(WFS_URL, params=params, timeout=timeout, follow_redirects=True)
        resposta.raise_for_status()
        dados = resposta.json()
    except (httpx.HTTPError, ValueError):
        return []

    ocorrencias: list[dict] = []
    for feature in dados.get("features", []):
        propriedades = feature.get("properties") or {}
        geometria = feature.get("geometry") or {}
        coordenadas = geometria.get("coordinates")
        identificador = propriedades.get("cd_identificador")
        if not coordenadas or identificador is None:
            continue
        longitude, latitude = _TRANSFORMER.transform(coordenadas[0], coordenadas[1])
        ocorrencias.append({
            "identificador": str(identificador),
            "latitude": latitude,
            "longitude": longitude,
            "data_ocorrencia": propriedades.get("dt_ocorrencia"),
            "subprefeitura": propriedades.get("nm_subprefeitura"),
        })
    return ocorrencias


def buscar_alagamentos(data_minima: str) -> list[dict]:
    """``data_minima`` no formato ISO (YYYY-MM-DD)."""
    return _buscar_camada("risco_ocorrencia_alagamento", data_minima)


def buscar_quedas_de_arvore(data_minima: str) -> list[dict]:
    return _buscar_camada("risco_ocorrencia_queda_arvore", data_minima)


def buscar_acidentes_transito(data_minima: str, *, timeout: float = 20.0) -> list[dict]:
    """Acidentes de trânsito levantados pela CET (camada ``acidente_cet``).

    Schema próprio: filtra por ``dt_acidente`` e traz feridos/óbitos/tipo em
    vez de subprefeitura — por isso não reaproveita ``_buscar_camada``.
    """
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": "geoportal:acidente_cet",
        "outputFormat": "application/json",
        "CQL_FILTER": f"dt_acidente >= '{data_minima}'",
    }
    try:
        resposta = httpx.get(WFS_URL, params=params, timeout=timeout, follow_redirects=True)
        resposta.raise_for_status()
        dados = resposta.json()
    except (httpx.HTTPError, ValueError):
        return []

    ocorrencias: list[dict] = []
    for feature in dados.get("features", []):
        propriedades = feature.get("properties") or {}
        geometria = feature.get("geometry") or {}
        coordenadas = geometria.get("coordinates")
        identificador = propriedades.get("cd_identificador")
        if not coordenadas or identificador is None:
            continue
        longitude, latitude = _TRANSFORMER.transform(coordenadas[0], coordenadas[1])
        ocorrencias.append({
            "identificador": str(identificador),
            "latitude": latitude,
            "longitude": longitude,
            "data_ocorrencia": propriedades.get("dt_acidente"),
            "logradouro": propriedades.get("nm_logradouro"),
            "tipo_acidente": propriedades.get("dc_tipo_acidente"),
            "feridos": propriedades.get("qt_ferido"),
            "fatais": propriedades.get("qt_fatal"),
        })
    return ocorrencias
