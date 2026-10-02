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


def test_alagamento_combina_chuva_e_aviso_inmet():
    entrada = EventoFusionInput(
        evento_id=8,
        tipo="alagamento",
        evidencias_ia=[],
        dados_clima=[
            DadoClima(chave="precipitacao_mm_h", valor_numerico=32.0, unidade="mm/h"),  # rampa 30->50 mm/h: 0.934
            DadoClima(chave="alerta_inmet_severidade", valor_numerico=4.0, unidade="indice_0_10"),  # "perigo potencial" -> 0.60
        ],
        fonte=FonteInfo(tipo="yolo", nome="MotSP YOLO Contínuo (alagamento)"),
    )
    r = calcular_confiabilidade(entrada)
    componente_clima = next(c for c in r.componentes if c.nome == "clima")
    assert "combina 2 fontes" in componente_clima.detalhe
    assert componente_clima.pontuacao == round((0.934 + 0.60) / 2, 4)


def _entrada_alagamento(dados_clima):
    return EventoFusionInput(
        evento_id=9,
        tipo="alagamento",
        evidencias_ia=[],
        dados_clima=dados_clima,
        fonte=FonteInfo(tipo="yolo", nome="MotSP YOLO Contínuo (alagamento)"),
    )


def test_alagamento_historico_reforca_quando_ha_chuva():
    chuva = DadoClima(chave="precipitacao_mm_h", valor_numerico=18.0, unidade="mm/h")
    hist = DadoClima(chave="historico_alagamento_indice", valor_numerico=9.0, unidade="indice_0_10")

    sem_hist = calcular_confiabilidade(_entrada_alagamento([chuva]))
    com_hist = calcular_confiabilidade(_entrada_alagamento([chuva, hist]))

    clima_sem = next(c for c in sem_hist.componentes if c.nome == "clima").pontuacao
    clima_com = next(c for c in com_hist.componentes if c.nome == "clima")
    assert clima_com.pontuacao > clima_sem
    assert "crônico" in clima_com.detalhe


def test_alagamento_sem_sinal_ao_vivo_e_sem_historico_cai_para_baixa():
    hist_zero = DadoClima(chave="historico_alagamento_indice", valor_numerico=0.0, unidade="indice_0_10")
    r = calcular_confiabilidade(_entrada_alagamento([hist_zero]))
    componente_clima = next(c for c in r.componentes if c.nome == "clima")
    assert componente_clima.pontuacao == 0.25
    assert "falso positivo" in componente_clima.detalhe


def test_alagamento_sem_historico_na_chave_reproduz_comportamento_antigo():
    chuva = DadoClima(chave="precipitacao_mm_h", valor_numerico=18.0, unidade="mm/h")
    r = calcular_confiabilidade(_entrada_alagamento([chuva]))
    componente_clima = next(c for c in r.componentes if c.nome == "clima")
    # 18 mm/h -> rampa 15->30 mm/h (0.78 -> 0.93), sem nenhum ajuste.
    assert componente_clima.pontuacao == 0.81
    assert "precipitação elevada" in componente_clima.detalhe


def test_transito_combina_indice_de_veiculos_e_tomtom():
    entrada = EventoFusionInput(
        evento_id=7,
        tipo="transito",
        evidencias_ia=[],
        dados_clima=[
            DadoClima(chave="indice_congestionamento", valor_numerico=3.0, unidade="indice_0_10"),
            DadoClima(chave="indice_congestionamento_tomtom", valor_numerico=8.0, unidade="indice_0_10"),
        ],
        fonte=FonteInfo(tipo="yolo", nome="MotSP YOLO Contínuo"),
    )
    r = calcular_confiabilidade(entrada)
    # média dos dois índices = 5.5/10 -> âncora "moderado" da rampa
    componente_clima = next(c for c in r.componentes if c.nome == "clima")
    assert "média de 2 fontes" in componente_clima.detalhe
    assert componente_clima.pontuacao == 0.72
    # 3 vs 8 é uma fonte desmentindo a outra: o contexto pesa menos que o base.
    assert componente_clima.peso_base == round(0.30 * 0.8, 4)
    assert "fontes divergem" in componente_clima.detalhe


def _entrada_transito(*indices):
    chaves = ("indice_congestionamento", "indice_congestionamento_tomtom")
    return EventoFusionInput(
        evento_id=10,
        tipo="transito",
        evidencias_ia=[EvidenciaIA(confianca=0.76, modelo_ia="YOLO11", classe_detectada="transito")],
        dados_clima=[
            DadoClima(chave=chave, valor_numerico=indice, unidade="indice_0_10")
            for chave, indice in zip(chaves, indices)
        ],
        fonte=FonteInfo(tipo="yolo", nome="MotSP YOLO Contínuo"),
    )


def _clima(resultado):
    return next(c for c in resultado.componentes if c.nome == "clima")


def test_transito_nota_contextual_e_continua_dentro_da_antiga_faixa():
    # Antes 4.5, 5.5 e 6.5 davam todos 0.72 (mesma faixa) -> contribuição fixa.
    notas = [_clima(calcular_confiabilidade(_entrada_transito(i))).pontuacao for i in (4.5, 5.5, 6.5)]
    assert notas[0] < notas[1] < notas[2]
    contribuicoes = {_clima(calcular_confiabilidade(_entrada_transito(i))).contribuicao for i in (4.5, 5.5, 6.5)}
    assert len(contribuicoes) == 3


def test_transito_peso_contextual_sobe_quando_fontes_concordam():
    concordam = calcular_confiabilidade(_entrada_transito(6.5, 6.5))
    uma_fonte = calcular_confiabilidade(_entrada_transito(6.5))
    clima_concordam, clima_uma = _clima(concordam), _clima(uma_fonte)

    assert clima_uma.peso_base == 0.30
    assert clima_concordam.peso_base == round(0.30 * 1.4, 4)
    assert clima_concordam.peso > clima_uma.peso
    assert "fontes concordam" in clima_concordam.detalhe
    # Mesma nota, mais peso: contexto corroborado empurra a confiabilidade.
    assert clima_concordam.pontuacao == clima_uma.pontuacao
    assert concordam.confiabilidade > uma_fonte.confiabilidade


def test_transito_peso_contextual_varia_continuamente_com_a_concordancia():
    pesos = [_clima(calcular_confiabilidade(_entrada_transito(6.0, t))).peso_base for t in (6.0, 5.0, 4.0, 3.0)]
    assert pesos == sorted(pesos, reverse=True)
    assert len(set(pesos)) == 4


def test_dimensoes_ausentes_nao_inventam_contribuicao():
    entrada = EventoFusionInput(
        evento_id=6,
        tipo="observacao_visual",
        evidencias_ia=[EvidenciaIA(confianca=0.735, modelo_ia="YOLO11n", classe_detectada="veiculo")],
        dados_clima=[],
        fonte=FonteInfo(tipo="yolo", nome="MotSP YOLO"),
    )
    resultado = calcular_confiabilidade(entrada)
    assert resultado.confiabilidade == 0.735
    assert resultado.componentes[0].peso == 1.0
    assert resultado.componentes[1].contribuicao == 0.0
    assert resultado.componentes[2].contribuicao == 0.0


if __name__ == "__main__":
    test_alagamento_com_clima_e_api()
    print("OK — testes de fusão passaram")
