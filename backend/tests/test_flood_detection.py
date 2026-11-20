"""Testes das regras de alagamento aplicadas a uma imagem.

O modelo, o clima, o INMET e o histórico são simulados, sem acessar a internet.
"""

import pytest

from app.services import flood_detection
from ml.detector import Deteccao


@pytest.fixture(autouse=True)
def _sem_clima_por_padrao(monkeypatch):
    """Evita chamar o Open-Meteo e o INMET de verdade e zera o histórico da via."""
    monkeypatch.setattr(flood_detection, "obter_condicoes_atuais", lambda _lat, _lon: {"disponivel": False})
    monkeypatch.setattr(flood_detection, "obter_aviso_ativo", lambda: {"disponivel": False})
    monkeypatch.setattr(flood_detection, "indice_historico", lambda _lat, _lon: (0.0, "sem histórico (fixture de teste)"))


def _deteccao_alagamento(confianca: float = 0.8) -> list[Deteccao]:
    # Mesmo formato que detectar_incidentes_imagem devolve de verdade.
    return [Deteccao(1, "alagamento", confianca, "critica", "alagamento", (0, 0, 50, 50), "flood")]


def _monta_imagem(monkeypatch, confianca: float = 0.8) -> None:
    monkeypatch.setattr(flood_detection, "detectar_incidentes_imagem", lambda _path, _threshold: _deteccao_alagamento(confianca))


def test_analisar_frame_sem_contexto_grava_so_o_historico(monkeypatch):
    _monta_imagem(monkeypatch, 0.81)

    analise = flood_detection.analisar_frame(b"frame-fake", -23.55, -46.63, "câmera teste")

    assert analise is not None
    # Evento.tipo é o que data_fusion.scores usa para escolher o cálculo.
    assert analise.deteccao.tipo == "alagamento"
    assert "câmera teste" in analise.fonte_nome
    assert analise.contexto == [("historico_alagamento_indice", 0.0, "indice_0_10")]


def test_analisar_frame_registra_chuva_aviso_e_historico(monkeypatch):
    _monta_imagem(monkeypatch)
    monkeypatch.setattr(flood_detection, "obter_condicoes_atuais", lambda _lat, _lon: {"disponivel": True, "chuva_mm": 22.0})
    monkeypatch.setattr(
        flood_detection,
        "obter_aviso_ativo",
        lambda: {"disponivel": True, "menciona_alagamento": True, "severidade_indice": 9.5, "severidade": "Grande Perigo"},
    )
    # A coordenada cai num ponto que alaga sempre.
    monkeypatch.setattr(flood_detection, "indice_historico", lambda _lat, _lon: (8.5, "Av. Exemplo (~80 m, recorrência cronico)"))

    analise = flood_detection.analisar_frame(b"frame-fake", -23.55, -46.63, "câmera teste")

    assert {chave: valor for chave, valor, _unidade in analise.contexto} == {
        "precipitacao_mm_h": 22.0, "alerta_inmet_severidade": 9.5, "historico_alagamento_indice": 8.5,
    }


def test_analisar_frame_descarta_contexto_incompleto(monkeypatch):
    """A API do clima responde sem o dado de chuva e o aviso do INMET não fala de alagamento."""
    _monta_imagem(monkeypatch)
    monkeypatch.setattr(flood_detection, "obter_condicoes_atuais", lambda _lat, _lon: {"disponivel": True, "chuva_mm": None})
    monkeypatch.setattr(
        flood_detection,
        "obter_aviso_ativo",
        lambda: {"disponivel": True, "menciona_alagamento": False, "severidade_indice": 9.5, "severidade": "Grande Perigo"},
    )

    analise = flood_detection.analisar_frame(b"frame-fake", -23.55, -46.63, "câmera teste")

    chaves = [chave for chave, _valor, _unidade in analise.contexto]
    assert chaves == ["historico_alagamento_indice"]


def test_sem_alagamento_devolve_nada_e_sem_modelo_avisa_o_ciclo(monkeypatch):
    monkeypatch.setattr(flood_detection, "detectar_incidentes_imagem", lambda _path, _threshold: [])
    assert flood_detection.analisar_frame(b"frame-fake", -23.55, -46.63, "câmera teste") is None

    def _falha(_path, _threshold):
        raise RuntimeError("modelo de incidentes indisponível")

    monkeypatch.setattr(flood_detection, "detectar_incidentes_imagem", _falha)
    with pytest.raises(RuntimeError):
        flood_detection.analisar_frame(b"frame-fake", -23.55, -46.63, "câmera teste")
