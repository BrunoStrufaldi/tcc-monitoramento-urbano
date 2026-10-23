"""Notas das duas dimensões do Data Fusion: IA e contexto."""

from data_fusion.models import DadoContexto, EvidenciaIA


def _clamp(valor: float, minimo: float = 0.0, maximo: float = 1.0) -> float:
    return max(minimo, min(maximo, valor))


def pontuar_ia(evidencias: list[EvidenciaIA]) -> tuple[float, str]:
    if not evidencias:
        return 0.0, "Sem evidência visual de IA, dimensão não utilizada"

    confiancas = [e.confianca for e in evidencias if e.confianca is not None]
    if not confiancas:
        return 0.0, "Evidência visual sem score, dimensão não utilizada"

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
    """Calcula a nota ligando os pontos de referência com retas.

    Assim cada pequena mudança no valor muda um pouco a nota, em vez de a nota
    pular de faixa em faixa.
    """
    if valor <= ancoras[0][0]:
        return ancoras[0][1]
    for (x0, y0), (x1, y1) in zip(ancoras, ancoras[1:]):
        if valor <= x1:
            return y0 + (y1 - y0) * (valor - x0) / (x1 - x0)
    return ancoras[-1][1]


# Pontos de referência da chuva (mm/h, nota). 5, 15 e 30 mm/h marcam chuva
# moderada, elevada e intensa.
_ANCORAS_CHUVA = ((0.0, 0.30), (5.0, 0.55), (15.0, 0.78), (30.0, 0.93), (50.0, 0.97))

# Pontos de referência do trânsito (índice de 0 a 10, nota).
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
    # Aqui a nota vai em degraus porque o INMET só tem três níveis de aviso.
    if indice >= 9:
        return 0.93, "aviso INMET de grande perigo ativo"
    if indice >= 6:
        return 0.80, "aviso INMET de perigo ativo"
    if indice >= 3:
        return 0.60, "aviso INMET de perigo potencial ativo"
    return 0.40, "sem aviso oficial relevante no momento"


def _alagamento_sem_sinal_ao_vivo(historico: float | None) -> tuple[float, str]:
    """Nota de um alagamento sem chuva e sem aviso do INMET.

    Se a via costuma alagar, a nota fica no meio. Se ela nunca alagou, a nota
    cai, porque provavelmente o modelo se enganou.
    """
    if historico is None:
        return 0.45, "Contexto sem precipitação nem aviso oficial registrados"
    if historico >= 4:
        return 0.45, f"Via com histórico de alagamento ({historico:.1f}/10), mas sem chuva nem aviso oficial agora"
    return 0.25, "Via sem histórico de alagamento e sem chuva/aviso oficial, provável falso positivo visual"


def _ajustar_por_historico(pontuacao: float, historico: float) -> tuple[float, str]:
    """Aumenta ou diminui a nota conforme o histórico de alagamento da via."""
    if historico >= 7:
        return pontuacao * 1.12, f"reforçado por ponto de alagamento crônico (histórico {historico:.1f}/10)"
    if historico >= 4:
        return pontuacao * 1.06, f"via com histórico recorrente de alagamento ({historico:.1f}/10)"
    if historico > 0:
        return pontuacao, f"histórico de alagamento baixo na via ({historico:.1f}/10)"
    return pontuacao * 0.90, "via sem histórico de alagamento, leve cautela"


def _pontuar_contexto_por_tipo(tipo: str, dados: list[DadoContexto]) -> tuple[float, str]:
    tipo_norm = tipo.lower().strip()
    valores = {d.chave.lower(): d.valor_numerico for d in dados if d.valor_numerico is not None}

    if tipo_norm == "alagamento":
        # A nota junta a chuva medida agora e o aviso do INMET, com a média dos
        # dois quando existem os dois. O histórico da via só ajusta essa nota e
        # nunca confirma o alagamento sozinho. Chuva de 0 mm/h conta como sem chuva.
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
            detalhe += ", contexto fraco para trânsito"
        return _interpolar(indice, _ANCORAS_TRANSITO), detalhe

    return 0.58, f"Contexto genérico para evento tipo '{tipo_norm}'"


def _indices_transito(valores: dict[str, float]) -> list[float]:
    return [
        valores[chave] for chave in ("indice_congestionamento", "indice_congestionamento_tomtom")
        if chave in valores
    ]


def _notas_por_fonte_ao_vivo(tipo: str, dados: list[DadoContexto]) -> list[float]:
    """Nota separada de cada fonte ao vivo do evento.

    O histórico de alagamento fica de fora, porque ele fala da via e não do que
    está acontecendo agora.
    """
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


# O peso do contexto muda conforme as fontes concordam: cai até 0.8x quando
# elas se contradizem e sobe até 1.4x quando dizem a mesma coisa.
FATOR_PESO_CONTEXTO_MIN = 0.8
FATOR_PESO_CONTEXTO_MAX = 1.4
_DIVERGENCIA_TOTAL = 0.4


def fator_peso_contexto(tipo: str, dados: list[DadoContexto]) -> tuple[float, str | None]:
    """Quanto o peso do contexto deve subir ou descer.

    Com uma fonte só, o peso fica igual. Com duas, ele sobe se elas concordam e
    desce se uma desmente a outra.
    """
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
        return 0.0, "Sem dados de contexto vinculados, dimensão não utilizada"
    return _pontuar_contexto_por_tipo(tipo, dados)

