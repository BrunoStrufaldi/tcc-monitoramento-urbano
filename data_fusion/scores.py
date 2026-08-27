"""Pontuação por dimensão: IA, clima e fonte oficial."""

from data_fusion.models import DadoClima, EvidenciaIA, FonteInfo

FONTES_OFICIAIS = frozenset({"api", "sensor", "data_fusion"})


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


def _pontuar_chuva(chuva: float) -> tuple[float, str]:
    if chuva >= 30:
        return 0.95, f"chuva intensa ({chuva:.1f} mm/h)"
    if chuva >= 15:
        return 0.82, f"precipitação elevada ({chuva:.1f} mm/h)"
    if chuva >= 5:
        return 0.62, f"chuva moderada ({chuva:.1f} mm/h)"
    return 0.35, f"baixa precipitação ({chuva:.1f} mm/h)"


def _pontuar_aviso_inmet(indice: float) -> tuple[float, str]:
    if indice >= 9:
        return 0.93, "aviso INMET de grande perigo ativo"
    if indice >= 6:
        return 0.80, "aviso INMET de perigo ativo"
    if indice >= 3:
        return 0.60, "aviso INMET de perigo potencial ativo"
    return 0.40, "sem aviso oficial relevante no momento"


def _pontuar_clima_por_tipo(tipo: str, dados: list[DadoClima]) -> tuple[float, str]:
    tipo_norm = tipo.lower().strip()
    valores = {d.chave.lower(): d.valor_numerico for d in dados if d.valor_numerico is not None}

    if tipo_norm == "alagamento":
        # Duas fontes independentes, mesmo padrão do trânsito (índice de
        # veículos + TomTom): chuva medida agora (Open-Meteo, sensor bruto) e
        # aviso oficial ativo do INMET (julgamento institucional) — quando as
        # duas existem, a pontuação é a média; sem nenhuma, cai pro genérico.
        chuva = valores.get("precipitacao_mm_h") or valores.get("precipitacao")
        aviso_inmet = valores.get("alerta_inmet_severidade")

        partes = [_pontuar_chuva(chuva)] if chuva is not None else []
        if aviso_inmet is not None:
            partes.append(_pontuar_aviso_inmet(aviso_inmet))

        if not partes:
            return 0.45, "Dados climáticos sem precipitação nem aviso oficial registrados"

        pontuacao = sum(p for p, _ in partes) / len(partes)
        detalhe = " + ".join(texto for _, texto in partes)
        origem = f" (combina {len(partes)} fontes)" if len(partes) > 1 else ""
        return pontuacao, f"Corroboração de alagamento: {detalhe}{origem}"

    if tipo_norm == "transito":
        indices = [
            valores[chave] for chave in ("indice_congestionamento", "indice_congestionamento_tomtom", "congestionamento")
            if chave in valores
        ]
        if not indices:
            return 0.50, "Dados de trânsito sem índice de congestionamento"
        indice = sum(indices) / len(indices)
        origem = f" (média de {len(indices)} fontes)" if len(indices) > 1 else ""
        if indice >= 7:
            return 0.92, f"Índice de congestionamento alto ({indice:.1f}/10){origem}"
        if indice >= 4:
            return 0.72, f"Congestionamento moderado ({indice:.1f}/10){origem}"
        return 0.40, f"Índice baixo ({indice:.1f}/10){origem} — contexto fraco para trânsito"

    return 0.58, f"Contexto climático genérico para evento tipo '{tipo_norm}'"


def pontuar_clima(tipo: str, dados: list[DadoClima]) -> tuple[float, str]:
    if not dados:
        return 0.0, "Sem dados climáticos vinculados — dimensão não utilizada"
    return _pontuar_clima_por_tipo(tipo, dados)


def pontuar_fonte_oficial(fonte: FonteInfo | None) -> tuple[float, str]:
    if fonte is None:
        return 0.0, "Sem fonte independente — dimensão não utilizada"

    tipo = fonte.tipo.lower().strip()

    if tipo in FONTES_OFICIAIS:
        base = 0.92 if tipo == "api" else 0.85 if tipo == "sensor" else 0.88
        if not fonte.ativo:
            base *= 0.85
        nome = fonte.nome or tipo
        return _clamp(base), f"Fonte oficial: {nome} ({tipo})"

    if tipo == "yolo":
        return 0.0, "YOLO já contabilizado na dimensão IA — aguarda fonte independente"

    if tipo == "manual":
        return 0.50, "Registro manual — validação oficial pendente"

    return 0.45, f"Fonte '{tipo}' com credibilidade intermediária"
