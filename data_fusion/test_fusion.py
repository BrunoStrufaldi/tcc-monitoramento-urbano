"""Testes do Data Fusion (python -m data_fusion.test_fusion na raiz do projeto)."""

from data_fusion.fusion import PESOS, _nivel_confiabilidade, calcular_confiabilidade
from data_fusion.models import DadoContexto, EvidenciaIA, EventoFusionInput


def _entrada_alagamento(dados_contexto):
    return EventoFusionInput(
        evento_id=9,
        tipo="alagamento",
        evidencias_ia=[],
        dados_contexto=dados_contexto,
    )


def _entrada_transito(*indices):
    chaves = ("indice_congestionamento", "indice_congestionamento_tomtom")
    return EventoFusionInput(
        evento_id=10,
        tipo="transito",
        evidencias_ia=[EvidenciaIA(confianca=0.76, modelo_ia="YOLO11", classe_detectada="transito")],
        dados_contexto=[
            DadoContexto(chave=chave, valor_numerico=indice, unidade="indice_0_10")
            for chave, indice in zip(chaves, indices)
        ],
    )


def _contexto(resultado):
    return next(c for c in resultado.componentes if c.nome == "contexto")


def test_pesos_e_dimensoes_ausentes():
    # IA com 4/7 e contexto com 3/7.
    assert round(PESOS["ia"], 4) == 0.5714
    assert round(PESOS["contexto"], 4) == 0.4286
    assert abs(sum(PESOS.values()) - 1.0) < 1e-9

    # Sem dado de contexto, a nota é só a da IA, sem inventar contribuição.
    entrada = EventoFusionInput(
        evento_id=6,
        tipo="observacao_visual",
        evidencias_ia=[EvidenciaIA(confianca=0.735, modelo_ia="YOLO11m", classe_detectada="veiculo")],
        dados_contexto=[],
    )
    resultado = calcular_confiabilidade(entrada)
    assert resultado.confiabilidade == 0.735
    assert resultado.componentes[0].peso == 1.0
    assert resultado.componentes[1].contribuicao == 0.0
    assert [c.nome for c in resultado.componentes] == ["ia", "contexto"]


def test_alagamento_pela_chuva():
    forte = calcular_confiabilidade(
        _entrada_alagamento([DadoContexto(chave="precipitacao_mm_h", valor_numerico=45.2, unidade="mm/h")])
    )
    assert forte.confiabilidade > 0.6
    assert forte.nivel in ("media", "alta")

    # 18 mm/h fica entre 15 e 30 mm/h (nota entre 0.78 e 0.93), sem outro ajuste.
    elevada = _contexto(calcular_confiabilidade(
        _entrada_alagamento([DadoContexto(chave="precipitacao_mm_h", valor_numerico=18.0, unidade="mm/h")])
    ))
    assert elevada.pontuacao == 0.81
    assert "precipitação elevada" in elevada.detalhe


def test_alagamento_combina_chuva_e_aviso_inmet():
    r = calcular_confiabilidade(_entrada_alagamento([
        DadoContexto(chave="precipitacao_mm_h", valor_numerico=32.0, unidade="mm/h"),  # rampa 30->50 mm/h: 0.934
        DadoContexto(chave="alerta_inmet_severidade", valor_numerico=4.0, unidade="indice_0_10"),  # "perigo potencial" -> 0.60
    ]))
    componente_contexto = _contexto(r)
    assert "combina 2 fontes" in componente_contexto.detalhe
    assert componente_contexto.pontuacao == round((0.934 + 0.60) / 2, 4)


def test_historico_da_via_reforca_ou_derruba_o_alagamento():
    chuva = DadoContexto(chave="precipitacao_mm_h", valor_numerico=18.0, unidade="mm/h")
    hist = DadoContexto(chave="historico_alagamento_indice", valor_numerico=9.0, unidade="indice_0_10")

    sem_hist = _contexto(calcular_confiabilidade(_entrada_alagamento([chuva])))
    com_hist = _contexto(calcular_confiabilidade(_entrada_alagamento([chuva, hist])))
    assert com_hist.pontuacao > sem_hist.pontuacao
    assert "crônico" in com_hist.detalhe

    # Sem chuva, sem aviso e numa via que nunca alagou, provavelmente é falso positivo.
    hist_zero = DadoContexto(chave="historico_alagamento_indice", valor_numerico=0.0, unidade="indice_0_10")
    sem_sinal = _contexto(calcular_confiabilidade(_entrada_alagamento([hist_zero])))
    assert sem_sinal.pontuacao == 0.25
    assert "falso positivo" in sem_sinal.detalhe


def test_transito_combina_veiculos_e_tomtom():
    # A média dos dois índices dá 5.5/10, que é congestionamento moderado.
    divergem = _contexto(calcular_confiabilidade(_entrada_transito(3.0, 8.0)))
    assert "média de 2 fontes" in divergem.detalhe
    assert divergem.pontuacao == 0.72


def test_pesos_fixos_com_uma_ou_duas_fontes():
    # Com as duas dimensões presentes, o peso é sempre 57% e 43%, como na fórmula.
    for entrada in (_entrada_transito(6.5), _entrada_transito(6.5, 6.5), _entrada_transito(3.0, 8.0)):
        resultado = calcular_confiabilidade(entrada)
        pesos = {c.nome: c.peso for c in resultado.componentes}
        assert pesos == {"ia": round(PESOS["ia"], 4), "contexto": round(PESOS["contexto"], 4)}


def test_transito_nota_varia_continuamente():
    # Índices diferentes precisam dar notas e contribuições diferentes.
    contextos = [_contexto(calcular_confiabilidade(_entrada_transito(i))) for i in (4.5, 5.5, 6.5)]
    assert contextos[0].pontuacao < contextos[1].pontuacao < contextos[2].pontuacao
    assert len({c.contribuicao for c in contextos}) == 3


def test_nivel_usa_o_valor_arredondado():
    # 79,77% aparece como 80% na tela, então o nível precisa ser alta.
    assert _nivel_confiabilidade(0.7977) == "alta"
    assert _nivel_confiabilidade(0.7949) == "media"
    assert _nivel_confiabilidade(0.5450) == "media"
    assert _nivel_confiabilidade(0.5449) == "baixa"


if __name__ == "__main__":
    for nome, teste in list(globals().items()):
        if nome.startswith("test_"):
            teste()
    print("OK, testes de fusão passaram")
