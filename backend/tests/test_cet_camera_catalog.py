"""Testes do catálogo de câmeras CET, busca por proximidade e frescor de frame."""

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx

from app.services.cet_camera_catalog import CAMERAS, camera_mais_proxima, frame_esta_desatualizado


def test_camera_mais_proxima_encontra_dentro_do_raio():
    referencia = CAMERAS[0]
    encontrada = camera_mais_proxima(referencia.latitude, referencia.longitude, raio_km=0.5)
    assert encontrada is not None
    assert encontrada.id == referencia.id


def test_camera_mais_proxima_retorna_none_fora_do_raio():
    # Coordenada longe de qualquer câmera do catálogo (interior de SP, zona rural)
    encontrada = camera_mais_proxima(-23.9, -47.5, raio_km=2.0)
    assert encontrada is None


def test_catalogo_tem_ids_unicos():
    ids = [camera.id for camera in CAMERAS]
    assert len(ids) == len(set(ids))


def _headers(last_modified: str | None) -> httpx.Headers:
    return httpx.Headers({"last-modified": last_modified} if last_modified else {})


def test_frame_recente_nao_e_desatualizado():
    agora_menos_10s = format_datetime(datetime.now(UTC) - timedelta(seconds=10), usegmt=True)
    assert frame_esta_desatualizado(_headers(agora_menos_10s), max_idade_segundos=300) is False


def test_frame_antigo_e_desatualizado():
    # Caso real que motivou isso: câmera 22 travada num JPEG de meses atrás.
    seis_meses_atras = format_datetime(datetime.now(UTC) - timedelta(days=180), usegmt=True)
    assert frame_esta_desatualizado(_headers(seis_meses_atras), max_idade_segundos=300) is True


def test_frame_sem_header_nao_e_tratado_como_desatualizado():
    """Last-Modified não é garantido por HTTP; sem ele, não dá pra provar que é velho."""
    assert frame_esta_desatualizado(_headers(None), max_idade_segundos=300) is False


def test_frame_com_header_invalido_nao_e_tratado_como_desatualizado():
    assert frame_esta_desatualizado(_headers("nao-e-uma-data-valida"), max_idade_segundos=300) is False
