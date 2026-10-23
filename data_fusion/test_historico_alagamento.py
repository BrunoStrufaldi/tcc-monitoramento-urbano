"""Testes do histórico de alagamento das vias (sem acessar a internet)."""

from data_fusion.historico_alagamento import indice_historico

# Ponto que alaga sempre, presente em data/pontos_alagamento_sp.json.
_NOVE_DE_JULHO_CIDADE_JARDIM = (-23.5875, -46.6905)


def test_indice_alto_no_ponto_cronico_e_menor_perto_dele():
    lat, lon = _NOVE_DE_JULHO_CIDADE_JARDIM
    sobre, descricao = indice_historico(lat, lon)
    assert sobre >= 8.0
    assert "Nove de Julho" in descricao

    # Uns 250 m ao norte: perto o bastante para contar, mas com nota menor.
    proximo, _ = indice_historico(lat + 0.00225, lon)
    assert 0.0 < proximo < sobre


def test_longe_ou_fora_do_raio_e_sem_historico():
    indice, descricao = indice_historico(-23.50, -46.50)
    assert indice == 0.0
    assert "sem histórico" in descricao

    # Uns 600 m: longe demais para contar (o limite padrão é 400 m).
    lat, lon = _NOVE_DE_JULHO_CIDADE_JARDIM
    indice, _ = indice_historico(lat + 0.0054, lon)
    assert indice == 0.0


if __name__ == "__main__":
    for nome, teste in list(globals().items()):
        if nome.startswith("test_"):
            teste()
    print("OK, testes do histórico de alagamento passaram")
