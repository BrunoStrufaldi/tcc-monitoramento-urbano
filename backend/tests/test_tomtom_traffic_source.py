"""Testes da fonte de trânsito da TomTom.

A chave vem da configuração (settings.tomtom_api_key), que lê o .env.
"""

import pytest

from app.config import settings
from app.services import tomtom_traffic_source


@pytest.fixture(autouse=True)
def _cache_vazio(monkeypatch):
    monkeypatch.setattr(tomtom_traffic_source, "_cache", {})


class _RespostaFalsa:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b'{"flowSegmentData": {"currentSpeed": 10, "freeFlowSpeed": 40, "confidence": 0.9, "roadClosure": false}}'


def test_resposta_valida_calcula_indice_de_congestionamento(monkeypatch):
    monkeypatch.setattr(settings, "tomtom_api_key", "chave-fake")
    monkeypatch.setattr(tomtom_traffic_source, "urlopen", lambda *_a, **_k: _RespostaFalsa())

    resultado = tomtom_traffic_source.obter_fluxo_transito(-23.55, -46.63)
    assert resultado["disponivel"] is True
    # 10 km/h numa via de 40 km/h livres: 75% mais lento, índice 7.5/10
    assert resultado["indice_congestionamento"] == 7.5
    assert resultado["via_fechada"] is False


def test_sem_chave_ou_sem_rede_retorna_indisponivel(monkeypatch):
    monkeypatch.setattr(settings, "tomtom_api_key", None)
    resultado = tomtom_traffic_source.obter_fluxo_transito(-23.55, -46.63)
    assert resultado["disponivel"] is False
    assert "TOMTOM_API_KEY" in resultado["erro"]

    def _falha(*_a, **_k):
        raise OSError("sem rede")

    monkeypatch.setattr(settings, "tomtom_api_key", "chave-fake")
    monkeypatch.setattr(tomtom_traffic_source, "urlopen", _falha)
    assert tomtom_traffic_source.obter_fluxo_transito(-23.55, -46.63)["disponivel"] is False


def test_leitura_boa_e_reaproveitada_e_falha_nao(monkeypatch):
    """A câmera sem evento é vista a cada 60 s. A TomTom só é consultada de novo depois do cache."""
    monkeypatch.setattr(settings, "tomtom_api_key", "chave-fake")
    chamadas: list[int] = []

    def _falha(*_a, **_k):
        chamadas.append(1)
        raise OSError("sem rede")

    monkeypatch.setattr(tomtom_traffic_source, "urlopen", _falha)
    tomtom_traffic_source.obter_fluxo_transito(-23.55, -46.63)
    tomtom_traffic_source.obter_fluxo_transito(-23.55, -46.63)
    assert len(chamadas) == 2

    def _ok(*_a, **_k):
        chamadas.append(1)
        return _RespostaFalsa()

    monkeypatch.setattr(tomtom_traffic_source, "urlopen", _ok)
    chamadas.clear()
    for _ in range(3):
        assert tomtom_traffic_source.obter_fluxo_transito(-23.55, -46.63)["indice_congestionamento"] == 7.5
    assert len(chamadas) == 1

    monkeypatch.setattr(settings, "gx_tomtom_cache_segundos", 0)
    tomtom_traffic_source.obter_fluxo_transito(-23.55, -46.63)
    assert len(chamadas) == 2
