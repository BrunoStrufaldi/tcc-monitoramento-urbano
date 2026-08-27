"""Testes da fonte de avisos meteorológicos oficiais ativos do INMET."""

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


def test_sem_aviso_cobrindo_o_municipio_retorna_indisponivel(monkeypatch):
    payload = {"hoje": [_aviso(geocodes="3100104,4100103")], "futuro": []}  # não inclui São Paulo capital
    monkeypatch.setattr(inmet_alert_source, "urlopen", lambda *_a, **_k: _RespostaFalsa(payload))

    resultado = inmet_alert_source.obter_aviso_ativo()
    assert resultado["disponivel"] is False


def test_aviso_ativo_cobrindo_sao_paulo_com_alagamento(monkeypatch):
    payload = {"hoje": [_aviso()], "futuro": []}
    monkeypatch.setattr(inmet_alert_source, "urlopen", lambda *_a, **_k: _RespostaFalsa(payload))

    resultado = inmet_alert_source.obter_aviso_ativo()
    assert resultado["disponivel"] is True
    assert resultado["descricao"] == "Tempestade"
    assert resultado["severidade_indice"] == 4.0
    assert resultado["menciona_alagamento"] is True


def test_aviso_sem_mencao_a_alagamento(monkeypatch):
    payload = {"hoje": [_aviso(riscos=["Vento costeiro forte, entre 40 e 60 km/h."])], "futuro": []}
    monkeypatch.setattr(inmet_alert_source, "urlopen", lambda *_a, **_k: _RespostaFalsa(payload))

    resultado = inmet_alert_source.obter_aviso_ativo()
    assert resultado["disponivel"] is True
    assert resultado["menciona_alagamento"] is False


def test_escolhe_o_aviso_mais_severo_quando_ha_varios(monkeypatch):
    payload = {
        "hoje": [
            _aviso(severidade="Perigo Potencial"),
            _aviso(severidade="Grande Perigo"),
            _aviso(severidade="Perigo"),
        ],
        "futuro": [],
    }
    monkeypatch.setattr(inmet_alert_source, "urlopen", lambda *_a, **_k: _RespostaFalsa(payload))

    resultado = inmet_alert_source.obter_aviso_ativo()
    assert resultado["severidade"] == "Grande Perigo"
    assert resultado["severidade_indice"] == 9.5


def test_falha_de_rede_nao_propaga(monkeypatch):
    def _falha(*_a, **_k):
        raise OSError("sem rede")

    monkeypatch.setattr(inmet_alert_source, "urlopen", _falha)

    resultado = inmet_alert_source.obter_aviso_ativo()
    assert resultado["disponivel"] is False
