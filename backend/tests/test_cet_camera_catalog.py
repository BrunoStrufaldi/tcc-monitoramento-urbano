"""Testes do catálogo de câmeras da CET, da busca por proximidade e da imagem travada."""

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx

from app.services.cet_camera_catalog import CAMERAS, camera_mais_proxima, frame_esta_desatualizado


def test_camera_mais_proxima_respeita_o_raio():
    referencia = CAMERAS[0]
    encontrada = camera_mais_proxima(referencia.latitude, referencia.longitude, raio_km=0.5)
    assert encontrada is not None
    assert encontrada.id == referencia.id

    # Coordenada longe de qualquer câmera do catálogo (interior de SP, zona rural)
    assert camera_mais_proxima(-23.9, -47.5, raio_km=2.0) is None

    ids = [camera.id for camera in CAMERAS]
    assert len(ids) == len(set(ids))


def _headers(last_modified: str | None) -> httpx.Headers:
    return httpx.Headers({"last-modified": last_modified} if last_modified else {})


def test_frame_antigo_e_desatualizado():
    agora_menos_10s = format_datetime(datetime.now(UTC) - timedelta(seconds=10), usegmt=True)
    assert frame_esta_desatualizado(_headers(agora_menos_10s), max_idade_segundos=300) is False

    # Câmera travada mandando a mesma foto de meses atrás.
    seis_meses_atras = format_datetime(datetime.now(UTC) - timedelta(days=180), usegmt=True)
    assert frame_esta_desatualizado(_headers(seis_meses_atras), max_idade_segundos=300) is True

    # Sem um Last-Modified válido não dá para saber se a imagem é velha.
    assert frame_esta_desatualizado(_headers(None), max_idade_segundos=300) is False
    assert frame_esta_desatualizado(_headers("nao-e-uma-data-valida"), max_idade_segundos=300) is False
