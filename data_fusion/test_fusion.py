"""Testes rápidos do módulo (python -m data_fusion.test_fusion na raiz do projeto)."""

from data_fusion.fusion import calcular_confiabilidade
from data_fusion.models import DadoClima, EvidenciaIA, EventoFusionInput, FonteInfo


def test_alagamento_com_clima_e_api():
    entrada = EventoFusionInput(
        evento_id=2,
        tipo="alagamento",
        evidencias_ia=[],
        dados_clima=[DadoClima(chave="precipitacao_mm_h", valor_numerico=45.2, unidade="mm/h")],
        fonte=FonteInfo(tipo="api", nome="API Prefeitura"),
    )
    r = calcular_confiabilidade(entrada)
    assert r.confiabilidade > 0.6
    assert r.nivel in ("media", "alta")


def test_incendio_com_ia():
    entrada = EventoFusionInput(
        evento_id=3,
        tipo="incendio",
        evidencias_ia=[EvidenciaIA(confianca=0.78, modelo_ia="yolov8n", classe_detectada="smoke")],
        dados_clima=[],
        fonte=FonteInfo(tipo="manual", nome="Painel manual"),
    )
    r = calcular_confiabilidade(entrada)
    assert 0.3 < r.confiabilidade < 0.9


if __name__ == "__main__":
    test_alagamento_com_clima_e_api()
    test_incendio_com_ia()
    print("OK — testes de fusão passaram")
