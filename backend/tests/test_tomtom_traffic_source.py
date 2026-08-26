"""Testes da fonte de trânsito ao vivo TomTom (Flow Segment Data)."""

from app.services import tomtom_traffic_source


def test_sem_chave_configurada_retorna_indisponivel(monkeypatch):
    monkeypatch.delenv("TOMTOM_API_KEY", raising=False)
    resultado = tomtom_traffic_source.obter_fluxo_transito(-23.55, -46.63)
    assert resultado["disponivel"] is False
    assert "TOMTOM_API_KEY" in resultado["erro"]


def test_resposta_valida_calcula_indice_de_congestionamento(monkeypatch):
    monkeypatch.setenv("TOMTOM_API_KEY", "chave-fake")

    class _RespostaFalsa:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"flowSegmentData": {"currentSpeed": 10, "freeFlowSpeed": 40, "confidence": 0.9, "roadClosure": false}}'

    monkeypatch.setattr(tomtom_traffic_source, "urlopen", lambda *_a, **_k: _RespostaFalsa())

    resultado = tomtom_traffic_source.obter_fluxo_transito(-23.55, -46.63)
    assert resultado["disponivel"] is True
    # currentSpeed 10 de 40 livre -> 75% mais lento que o ideal -> índice 7.5/10
    assert resultado["indice_congestionamento"] == 7.5
    assert resultado["via_fechada"] is False


def test_falha_de_rede_nao_propaga(monkeypatch):
    monkeypatch.setenv("TOMTOM_API_KEY", "chave-fake")

    def _falha(*_a, **_k):
        raise OSError("sem rede")

    monkeypatch.setattr(tomtom_traffic_source, "urlopen", _falha)

    resultado = tomtom_traffic_source.obter_fluxo_transito(-23.55, -46.63)
    assert resultado["disponivel"] is False
