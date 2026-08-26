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


def test_arvore_caida_com_vento_forte():
    entrada = EventoFusionInput(
        evento_id=4,
        tipo="arvore_caida",
        evidencias_ia=[],
        dados_clima=[DadoClima(chave="vento_kmh", valor_numerico=72.0, unidade="km/h")],
        fonte=FonteInfo(tipo="api", nome="Open-Meteo"),
    )
    r = calcular_confiabilidade(entrada)
    assert r.confiabilidade > 0.6
    assert r.nivel in ("media", "alta")


def test_transito_combina_indice_de_veiculos_e_tomtom():
    entrada = EventoFusionInput(
        evento_id=7,
        tipo="transito",
        evidencias_ia=[],
        dados_clima=[
            DadoClima(chave="indice_congestionamento", valor_numerico=3.0, unidade="indice_0_10"),
            DadoClima(chave="indice_congestionamento_tomtom", valor_numerico=8.0, unidade="indice_0_10"),
        ],
        fonte=FonteInfo(tipo="yolo", nome="GX YOLO Contínuo"),
    )
    r = calcular_confiabilidade(entrada)
    # média dos dois índices = 5.5/10 -> faixa "moderado"
    componente_clima = next(c for c in r.componentes if c.nome == "clima")
    assert "média de 2 fontes" in componente_clima.detalhe
    assert componente_clima.pontuacao == 0.72


def test_dimensoes_ausentes_nao_inventam_contribuicao():
    entrada = EventoFusionInput(
        evento_id=6,
        tipo="observacao_visual",
        evidencias_ia=[EvidenciaIA(confianca=0.735, modelo_ia="YOLO11n", classe_detectada="veiculo")],
        dados_clima=[],
        fonte=FonteInfo(tipo="yolo", nome="GX YOLO"),
    )
    resultado = calcular_confiabilidade(entrada)
    assert resultado.confiabilidade == 0.735
    assert resultado.componentes[0].peso == 1.0
    assert resultado.componentes[1].contribuicao == 0.0
    assert resultado.componentes[2].contribuicao == 0.0


if __name__ == "__main__":
    test_alagamento_com_clima_e_api()
    test_incendio_com_ia()
    test_arvore_caida_com_vento_forte()
    print("OK — testes de fusão passaram")
