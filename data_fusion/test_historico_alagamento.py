"""Testes do prior espacial de alagamento (lookup local, sem rede)."""

from data_fusion.historico_alagamento import indice_historico

# Ponto crônico presente em data/pontos_alagamento_sp.json.
_NOVE_DE_JULHO_CIDADE_JARDIM = (-23.5875, -46.6905)


def test_sobre_ponto_cronico_retorna_indice_alto():
    indice, descricao = indice_historico(*_NOVE_DE_JULHO_CIDADE_JARDIM)
    assert indice >= 8.0
    assert "Nove de Julho" in descricao


def test_distancia_intermediaria_reduz_o_indice():
    lat, lon = _NOVE_DE_JULHO_CIDADE_JARDIM
    # ~250 m ao norte (0.00225° de latitude) — dentro do raio total, fora do pleno.
    proximo, _ = indice_historico(lat + 0.00225, lon)
    sobre, _ = indice_historico(lat, lon)
    assert 0.0 < proximo < sobre


def test_longe_de_qualquer_ponto_retorna_zero():
    indice, descricao = indice_historico(-23.50, -46.50)
    assert indice == 0.0
    assert "sem histórico" in descricao


def test_fora_do_raio_total_e_tratado_como_sem_historico():
    lat, lon = _NOVE_DE_JULHO_CIDADE_JARDIM
    # ~600 m — além do raio_total_m padrão (400 m).
    indice, _ = indice_historico(lat + 0.0054, lon)
    assert indice == 0.0


if __name__ == "__main__":
    test_sobre_ponto_cronico_retorna_indice_alto()
    test_longe_de_qualquer_ponto_retorna_zero()
    print("OK — testes do prior histórico de alagamento passaram")
