"""Testes das regras de trânsito aplicadas a uma imagem.

O YOLO e a TomTom são simulados, sem acessar a internet.
"""

import pytest

from app.services import live_detection
from ml.detector import Deteccao


def _veiculos(quantidade: int) -> list[Deteccao]:
    return [
        Deteccao(8, "veiculo", 0.8, "baixa", "observacao_visual", (i * 10, 0, i * 10 + 8, 8), "car")
        for i in range(quantidade)
    ]


@pytest.fixture(autouse=True)
def _sem_tomtom_por_padrao(monkeypatch):
    """Evita chamar a TomTom de verdade nos testes."""
    monkeypatch.setattr(live_detection, "obter_fluxo_transito", lambda _lat, _lon: {"disponivel": False})


def _monta_imagem(monkeypatch, veiculos: int, fluxo_tomtom: dict) -> None:
    monkeypatch.setattr(live_detection, "detectar_imagem_real", lambda _path, _threshold: _veiculos(veiculos))
    monkeypatch.setattr(live_detection, "obter_fluxo_transito", lambda _lat, _lon: fluxo_tomtom)


def test_gatilho_de_tres_faixas_com_a_tomtom():
    """Contagem alta cria direto, contagem média depende da TomTom e contagem baixa precisa dela."""
    sem_tomtom = {"disponivel": False}
    casos = [
        # (veículos, resposta da TomTom, cria?, trecho do motivo)
        (16, sem_tomtom, True, "contagem alta"),
        (13, {"disponivel": True, "via_fechada": True, "indice_congestionamento": 0.0}, True, "fechada"),
        (13, sem_tomtom, True, "sem TomTom"),
        (13, {"disponivel": True, "indice_congestionamento": 5.0}, True, "confirma lentidão"),
        (13, {"disponivel": True, "indice_congestionamento": 1.5}, False, "fluindo"),
        (6, {"disponivel": True, "indice_congestionamento": 5.5}, True, "sustenta a contagem baixa"),
        (6, sem_tomtom, False, "nada a corroborar"),
        (6, {"disponivel": True, "indice_congestionamento": None}, False, "nada a corroborar"),
        (6, {"disponivel": True, "indice_congestionamento": 1.0}, False, "fluindo"),
    ]
    for veiculos, fluxo, esperado, trecho in casos:
        criar, motivo = live_detection._avaliar_gatilho_transito(veiculos, fluxo)
        assert criar is esperado, (veiculos, fluxo)
        assert trecho in motivo, (veiculos, fluxo)


def test_analisar_frame_com_as_duas_fontes(monkeypatch):
    _monta_imagem(monkeypatch, 6, {"disponivel": True, "indice_congestionamento": 8.0})

    analise = live_detection.analisar_frame(b"frame-fake", -23.55, -46.63, "câmera teste")

    assert analise is not None
    assert analise.deteccao.tipo == "transito"
    assert len(analise.deteccoes_para_anotar) == 6
    assert "câmera teste" in analise.fonte_nome
    assert analise.contexto == [
        ("indice_congestionamento", 3.0, "indice_0_10"),
        ("indice_congestionamento_tomtom", 8.0, "indice_0_10"),
    ]


def test_analisar_frame_recusado_pela_tomtom(monkeypatch):
    _monta_imagem(monkeypatch, 13, {"disponivel": True, "indice_congestionamento": 1.0})
    assert live_detection.analisar_frame(b"frame-fake", -23.55, -46.63) is None


def test_poucos_veiculos_nem_consulta_a_tomtom(monkeypatch):
    consultas: list[int] = []

    def _tomtom(_lat, _lon):
        consultas.append(1)
        return {"disponivel": True, "indice_congestionamento": 9.0}

    _monta_imagem(monkeypatch, 3, {})
    monkeypatch.setattr(live_detection, "obter_fluxo_transito", _tomtom)

    assert live_detection.analisar_frame(b"frame-fake", -23.55, -46.63) is None
    assert consultas == []


def test_modelo_indisponivel_avisa_o_ciclo(monkeypatch):
    """Sem modelo não dá para dizer que não há trânsito, então o erro sobe."""
    def _falha(_path, _threshold):
        raise RuntimeError("modelo indisponível")

    monkeypatch.setattr(live_detection, "detectar_imagem_real", _falha)
    with pytest.raises(RuntimeError):
        live_detection.analisar_frame(b"frame-fake", -23.55, -46.63)
