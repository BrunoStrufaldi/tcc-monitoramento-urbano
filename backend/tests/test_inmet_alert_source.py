"""Testes dos avisos do INMET."""

import json

from app.services import inmet_alert_source


class _RespostaFalsa:
    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def _aviso(*, severidade: str = "Perigo Potencial", geocodes: str = "3550308,3100104", riscos: list[str] | None = None) -> dict:
    return {
        "descricao": "Tempestade",
        "severidade": severidade,
        "geocodes": geocodes,
        "riscos": riscos if riscos is not None else ["Chuva entre 20 e 30 mm/h, risco de alagamentos."],
        "data_fim": "2026-08-26T00:00:00.000Z",
        "hora_fim": "23:59",
    }


def _responde(monkeypatch, *avisos: dict) -> dict:
    payload = {"hoje": list(avisos), "futuro": []}
    monkeypatch.setattr(inmet_alert_source, "urlopen", lambda *_a, **_k: _RespostaFalsa(payload))
    return inmet_alert_source.obter_aviso_ativo()


def test_escolhe_o_aviso_mais_severo_que_cobre_sao_paulo(monkeypatch):
    resultado = _responde(monkeypatch, _aviso())
    assert resultado["disponivel"] is True
    assert resultado["descricao"] == "Tempestade"
    assert resultado["severidade_indice"] == 4.0
    assert resultado["menciona_alagamento"] is True

    resultado = _responde(
        monkeypatch,
        _aviso(severidade="Perigo Potencial"),
        _aviso(severidade="Grande Perigo"),
        _aviso(severidade="Perigo"),
    )
    assert resultado["severidade"] == "Grande Perigo"
    assert resultado["severidade_indice"] == 9.5


def test_aviso_de_outro_municipio_ou_sem_alagamento(monkeypatch):
    # Não inclui São Paulo capital.
    assert _responde(monkeypatch, _aviso(geocodes="3100104,4100103"))["disponivel"] is False

    resultado = _responde(monkeypatch, _aviso(riscos=["Vento costeiro forte, entre 40 e 60 km/h."]))
    assert resultado["disponivel"] is True
    assert resultado["menciona_alagamento"] is False


def test_falha_de_rede_nao_propaga(monkeypatch):
    def _falha(*_a, **_k):
        raise OSError("sem rede")

    monkeypatch.setattr(inmet_alert_source, "urlopen", _falha)

    resultado = inmet_alert_source.obter_aviso_ativo()
    assert resultado["disponivel"] is False
