"""Catálogo das câmeras públicas da CET-SP expostas em cameras.cetsp.com.br.

Não existe uma API de listagem — este conjunto foi extraído do HTML público de
``https://cameras.cetsp.com.br/View/Cam.aspx`` (11 câmeras "favoritas" que o
próprio site expõe, cada uma com ID e nome do cruzamento; confirmado em
2026-08-26). É um subconjunto pequeno da rede real de câmeras da CET, não a
cobertura completa da cidade.

As coordenadas foram geocodificadas a partir do nome do cruzamento (Nominatim/
OpenStreetMap) — são aproximações de rua/quarteirão, não o ponto exato do
poste da câmera. Suficiente para achar "câmera mais próxima dentro de X km",
não para navegação de precisão.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    CameraCET(22, "Paulista - Metrô Consolação", -23.5572, -46.6610),
)


def _distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância aproximada em linha reta (haversine), raio da Terra 6371 km."""
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
