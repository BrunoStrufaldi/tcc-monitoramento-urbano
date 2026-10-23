"""Lista das câmeras públicas da CET-SP usadas pelo sistema.

A CET não tem uma API com a lista de câmeras, então elas foram tiradas do site
cameras.cetsp.com.br. São 10 câmeras. As coordenadas foram calculadas a partir
do nome do cruzamento, então são aproximadas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from math import atan2, cos, radians, sin, sqrt

SNAPSHOT_URL_TEMPLATE = "https://cameras.cetsp.com.br/Cams/{id}/1.jpg"


@dataclass(frozen=True)
class CameraCET:
    id: int
    nome: str
    latitude: float
    longitude: float

    @property
    def snapshot_url(self) -> str:
        return SNAPSHOT_URL_TEMPLATE.format(id=self.id)


CAMERAS: tuple[CameraCET, ...] = (
    CameraCET(225, "Ascendino Reis - R Pedro de Toledo", -23.5975, -46.6508),
    CameraCET(184, "Brasil - Av Brig Luis Antônio", -23.5608, -46.6437),
    CameraCET(195, "Brasil - Av Henrique Schaumann", -23.5643, -46.6780),
    CameraCET(210, "Brig Luis Antônio - Al Santos", -23.5659, -46.6532),
    CameraCET(220, "Cidade Jardim - Av Nove de Julho", -23.5867, -46.6900),
    CameraCET(180, "Consolação - R Caio Prado", -23.5492, -46.6485),
    CameraCET(222, "Hélio Pellegrino - R Diogo Jácome", -23.5983, -46.6684),
    CameraCET(224, "Ibirapuera - R Ipê", -23.5877, -46.6585),
    CameraCET(200, "Iguatemi - Av Brig Faria Lima", -23.5772, -46.6880),
    CameraCET(23, "Paulista - Av Brigadeiro Luiz Antônio", -23.5576, -46.6606),
)


def _distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância aproximada em linha reta entre dois pontos, em km."""
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return r * 2 * atan2(sqrt(a), sqrt(1 - a))


def camera_mais_proxima(latitude: float, longitude: float, raio_km: float) -> CameraCET | None:
    candidatas = sorted(CAMERAS, key=lambda cam: _distancia_km(latitude, longitude, cam.latitude, cam.longitude))
    if not candidatas:
        return None
    mais_proxima = candidatas[0]
    if _distancia_km(latitude, longitude, mais_proxima.latitude, mais_proxima.longitude) > raio_km:
        return None
    return mais_proxima


def frame_esta_desatualizado(headers, max_idade_segundos: float) -> bool:
    """Diz se a imagem da câmera está velha, ou seja, se a câmera travou.

    A CET às vezes trava uma câmera e ela continua mandando a mesma foto antiga.
    A data da imagem vem no cabeçalho Last-Modified. Se ele não vier, a imagem
    é considerada atual.
    """
    valor = headers.get("last-modified")
    if not valor:
        return False
    try:
        modificado_em = parsedate_to_datetime(valor)
    except (TypeError, ValueError):
        return False
    if modificado_em.tzinfo is None:
        modificado_em = modificado_em.replace(tzinfo=UTC)
    idade_segundos = (datetime.now(UTC) - modificado_em).total_seconds()
    return idade_segundos > max_idade_segundos
