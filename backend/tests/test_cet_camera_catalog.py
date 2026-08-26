"""Testes do catálogo de câmeras CET e da busca por proximidade."""

from app.services.cet_camera_catalog import CAMERAS, camera_mais_proxima


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
