"""Pontuação por dimensão: IA e contexto."""

from data_fusion.models import DadoContexto, EvidenciaIA


def _clamp(valor: float, minimo: float = 0.0, maximo: float = 1.0) -> float:
    return max(minimo, min(maximo, valor))


def pontuar_ia(evidencias: list[EvidenciaIA]) -> tuple[float, str]:
    if not evidencias:
        return 0.0, "Sem evidência visual de IA — dimensão não utilizada"

    confiancas = [e.confianca for e in evidencias if e.confianca is not None]
    if not confiancas:
        return 0.0, "Evidência visual sem score — dimensão não utilizada"

    melhor = max(confiancas)
    tem_modelo = any(e.modelo_ia for e in evidencias)
    classes = [e.classe_detectada for e in evidencias if e.classe_detectada]
    detalhe = f"Melhor detecção IA: {melhor:.0%}"
    if classes:
        detalhe += f" ({', '.join(classes[:2])})"
    if tem_modelo:
        detalhe += " · modelo validado"

    return _clamp(melhor), detalhe


def _interpolar(valor: float, ancoras: tuple[tuple[float, float], ...]) -> float:
    """Interpolação linear por trechos entre âncoras (x, nota), saturando nas pontas.

    Substitui as faixas em degrau: com degrau, todo índice de trânsito entre 4 e
    7 virava a mesma nota 0.72 — e, com o peso rateado de 43%, a mesma
    contribuição de 31% em praticamente todo evento, por mais forte ou fraco que
    fosse o sinal. Com a rampa, cada décimo do índice mexe na nota."""
    if valor <= ancoras[0][0]:
        return ancoras[0][1]
    for (x0, y0), (x1, y1) in zip(ancoras, ancoras[1:]):
        if valor <= x1:
            return y0 + (y1 - y0) * (valor - x0) / (x1 - x0)
    return ancoras[-1][1]


# Âncoras (mm/h, nota). Os limiares 5/15/30 mm/h seguem as faixas de
# intensidade usadas antes (moderada, elevada, intensa).
_ANCORAS_CHUVA = ((0.0, 0.30), (5.0, 0.55), (15.0, 0.78), (30.0, 0.93), (50.0, 0.97))

# Âncoras (índice 0-10, nota). Cada âncora interna fica no meio de uma das
# antigas faixas e reproduz a nota que ela dava (5.5 -> 0.72, 8 -> 0.92).
_ANCORAS_TRANSITO = ((0.0, 0.25), (3.0, 0.45), (5.5, 0.72), (8.0, 0.92), (10.0, 0.97))


def _rotulo_chuva(chuva: float) -> str:
    if chuva >= 30:
        return "chuva intensa"
    if chuva >= 15:
        return "precipitação elevada"
    if chuva >= 5:
        return "chuva moderada"
    return "baixa precipitação"


def _pontuar_chuva(chuva: float) -> tuple[float, str]:
    return _interpolar(chuva, _ANCORAS_CHUVA), f"{_rotulo_chuva(chuva)} ({chuva:.1f} mm/h)"


def _pontuar_aviso_inmet(indice: float) -> tuple[float, str]:
    # Fica em degrau de propósito: o INMET emite níveis categóricos (perigo
    # potencial / perigo / grande perigo), não uma medida contínua.
    if indice >= 9:
        return 0.93, "aviso INMET de grande perigo ativo"
    if indice >= 6:
        return 0.80, "aviso INMET de perigo ativo"
    if indice >= 3:
        return 0.60, "aviso INMET de perigo potencial ativo"
    return 0.40, "sem aviso oficial relevante no momento"


def _alagamento_sem_sinal_ao_vivo(historico: float | None) -> tuple[float, str]:
    """Alagamento sem chuva medida nem aviso INMET ativo. Sem o prior histórico
    (evento não-autônomo, ex.: registro manual) mantém o genérico; com ele, uma
    via reconhecidamente crítica segura a pontuação e a ausência de histórico a
    derruba — o caso clássico de falso positivo do modelo de incidentes."""
    if historico is None:
        return 0.45, "Contexto sem precipitação nem aviso oficial registrados"
    if historico >= 4:
        return 0.45, f"Via com histórico de alagamento ({historico:.1f}/10), mas sem chuva nem aviso oficial agora"
    return 0.25, "Via sem histórico de alagamento e sem chuva/aviso oficial — provável falso positivo visual"


def _ajustar_por_historico(pontuacao: float, historico: float) -> tuple[float, str]:
    """Modifica a pontuação de contexto já corroborada por sinal ao vivo conforme o
    histórico de alagamento da via (prior espacial, nunca dimensão isolada)."""
    if historico >= 7:
        return pontuacao * 1.12, f"reforçado por ponto de alagamento crônico (histórico {historico:.1f}/10)"
    if historico >= 4:
        return pontuacao * 1.06, f"via com histórico recorrente de alagamento ({historico:.1f}/10)"
    if historico > 0:
        return pontuacao, f"histórico de alagamento baixo na via ({historico:.1f}/10)"
    return pontuacao * 0.90, "via sem histórico de alagamento — leve cautela"


def _pontuar_contexto_por_tipo(tipo: str, dados: list[DadoContexto]) -> tuple[float, str]:
    tipo_norm = tipo.lower().strip()
    valores = {d.chave.lower(): d.valor_numerico for d in dados if d.valor_numerico is not None}

    if tipo_norm == "alagamento":
        # Dois sinais independentes ao vivo, mesmo padrão do trânsito (índice de
        # veículos + TomTom): chuva medida agora (Open-Meteo, sensor bruto) e
        # aviso oficial ativo do INMET (julgamento institucional) — quando os
        # dois existem, a pontuação é a média. Mais um prior espacial estático: o
        # histórico de alagamento da via (data_fusion.historico_alagamento), que
        # nunca confirma sozinho — só reforça quando já há sinal ao vivo, e cuja
        # ausência num ponto sem chuva/aviso derruba a pontuação.
        # 0.0 mm/h conta como "sem sinal de chuva", não como leitura: cai em
        # _alagamento_sem_sinal_ao_vivo (comportamento de sempre, mantido).
        chuva = valores.get("precipitacao_mm_h") or None
        aviso_inmet = valores.get("alerta_inmet_severidade")
        historico = valores.get("historico_alagamento_indice")

        partes = [_pontuar_chuva(chuva)] if chuva is not None else []
        if aviso_inmet is not None:
            partes.append(_pontuar_aviso_inmet(aviso_inmet))

        if not partes:
            return _alagamento_sem_sinal_ao_vivo(historico)

        pontuacao = sum(p for p, _ in partes) / len(partes)
        detalhe = " + ".join(texto for _, texto in partes)
        origem = f" (combina {len(partes)} fontes)" if len(partes) > 1 else ""

        if historico is not None:
            pontuacao, nota_historico = _ajustar_por_historico(pontuacao, historico)
            detalhe += f" · {nota_historico}"

        return _clamp(pontuacao), f"Corroboração de alagamento: {detalhe}{origem}"

    if tipo_norm == "transito":
        indices = _indices_transito(valores)
        if not indices:
            return 0.50, "Dados de trânsito sem índice de congestionamento"
        indice = sum(indices) / len(indices)
        origem = f" (média de {len(indices)} fontes)" if len(indices) > 1 else ""
        if indice >= 7:
            rotulo = "Índice de congestionamento alto"
        elif indice >= 4:
            rotulo = "Congestionamento moderado"
        else:
            rotulo = "Índice baixo"
        detalhe = f"{rotulo} ({indice:.1f}/10){origem}"
        if indice < 4:
            detalhe += " — contexto fraco para trânsito"
        return _interpolar(indice, _ANCORAS_TRANSITO), detalhe

    return 0.58, f"Contexto genérico para evento tipo '{tipo_norm}'"


def _indices_transito(valores: dict[str, float]) -> list[float]:
    return [
        valores[chave] for chave in ("indice_congestionamento", "indice_congestionamento_tomtom")
        if chave in valores
    ]


def _notas_por_fonte_ao_vivo(tipo: str, dados: list[DadoContexto]) -> list[float]:
    """Nota isolada de cada fonte contextual independente e ao vivo do evento.

    Trânsito: contagem de veículos do frame e TomTom. Alagamento: chuva medida
    (Open-Meteo) e aviso do INMET. O histórico de alagamento fica de fora de
    propósito — é prior estático da via, não uma segunda testemunha do agora."""
    tipo_norm = tipo.lower().strip()
    valores = {d.chave.lower(): d.valor_numerico for d in dados if d.valor_numerico is not None}
    if tipo_norm == "transito":
        return [_interpolar(i, _ANCORAS_TRANSITO) for i in _indices_transito(valores)]
    if tipo_norm == "alagamento":
        notas = []
        chuva = valores.get("precipitacao_mm_h") or None
        if chuva is not None:
            notas.append(_pontuar_chuva(chuva)[0])
        if valores.get("alerta_inmet_severidade") is not None:
            notas.append(_pontuar_aviso_inmet(valores["alerta_inmet_severidade"])[0])
        return notas
    return []


# Peso do dado contextual conforme a concordância entre fontes independentes:
# 0.8x quando se contradizem, 1.4x quando dizem a mesma coisa. Divergência de
# nota a partir de _DIVERGENCIA_TOTAL conta como contradição completa.
FATOR_PESO_CONTEXTO_MIN = 0.8
FATOR_PESO_CONTEXTO_MAX = 1.4
_DIVERGENCIA_TOTAL = 0.4


def fator_peso_contexto(tipo: str, dados: list[DadoContexto]) -> tuple[float, str | None]:
    """Multiplicador do peso-base da dimensão contextual.

    Peso fixo tratava igual um índice isolado e dois sensores independentes
    batendo o mesmo número. Aqui o peso flexiona: com uma fonte só fica no
    base (1.0x); com duas, sobe linearmente com a concordância entre elas até
    1.4x e desce até 0.8x quando uma desmente a outra — contexto contraditório
    é contexto incerto, e deve pesar menos que a evidência visual."""
    notas = _notas_por_fonte_ao_vivo(tipo, dados)
    if len(notas) < 2:
        return 1.0, None
    divergencia = max(notas) - min(notas)
    concordancia = _clamp(1 - divergencia / _DIVERGENCIA_TOTAL)
    fator = FATOR_PESO_CONTEXTO_MIN + (FATOR_PESO_CONTEXTO_MAX - FATOR_PESO_CONTEXTO_MIN) * concordancia
    if concordancia >= 0.75:
        resumo = "fontes concordam"
    elif concordancia >= 0.35:
        resumo = "fontes concordam em parte"
    else:
        resumo = "fontes divergem"
    return round(fator, 4), f"peso ajustado {fator:.2f}x ({resumo}, concordância {concordancia:.0%})"


def pontuar_contexto(tipo: str, dados: list[DadoContexto]) -> tuple[float, str]:
    if not dados:
        return 0.0, "Sem dados de contexto vinculados — dimensão não utilizada"
    return _pontuar_contexto_por_tipo(tipo, dados)

