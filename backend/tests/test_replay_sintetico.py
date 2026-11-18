"""Confere que o replay sintético continua dando a saída esperada."""

import replay_sintetico


def test_replay_sintetico_bate_com_a_saida_esperada():
    obtida = "\n".join(replay_sintetico.executar()) + "\n"
    esperada = replay_sintetico.SAIDA_ESPERADA.read_text(encoding="utf-8")
    assert obtida == esperada
