"""Pontuação por dimensão: IA, clima e fonte oficial."""

from data_fusion.models import DadoClima, EvidenciaIA, FonteInfo

# Tipos de fonte considerados oficiais (prefeitura, órgãos, sensores certificados)
FONTES_OFICIAIS = frozenset({"api", "sensor", "data_fusion"})


def _clamp(valor: float, minimo: float = 0.0, maximo: float = 1.0) -> float:
    return max(minimo, min(maximo, valor))


def pontuar_ia(evidencias: list[EvidenciaIA]) -> tuple[float, str]:
    if not evidencias:
        return 0.25, "Sem evidência visual de IA"

    confiancas = [e.confianca for e in evidencias if e.confianca is not None]
    if not confiancas:
        return 0.45, "Evidência visual presente, sem score de confiança"

    melhor = max(confiancas)
    tem_modelo = any(e.modelo_ia for e in evidencias)
    bonus = 0.05 if tem_modelo else 0.0
    classes = [e.classe_detectada for e in evidencias if e.classe_detectada]
    detalhe = f"Melhor detecção IA: {melhor:.0%}"
    if classes:
        detalhe += f" ({', '.join(classes[:2])})"
    if tem_modelo:
        detalhe += " · modelo validado"

    return _clamp(melhor + bonus), detalhe


def _pontuar_clima_por_tipo(tipo: str, dados: list[DadoClima]) -> tuple[float, str]:
    tipo_norm = tipo.lower().strip()
    valores = {d.chave.lower(): d.valor_numerico for d in dados if d.valor_numerico is not None}

    if tipo_norm == "alagamento":
        chuva = valores.get("precipitacao_mm_h") or valores.get("precipitacao")
        if chuva is None:
            return 0.45, "Dados climáticos sem precipitação registrada"
        if chuva >= 30:
            return 0.95, f"Chuva intensa ({chuva:.1f} mm/h) corrobora alagamento"
        if chuva >= 15:
            return 0.82, f"Precipitação elevada ({chuva:.1f} mm/h)"
        if chuva >= 5:
            return 0.62, f"Chuva moderada ({chuva:.1f} mm/h)"
        return 0.35, f"Baixa precipitação ({chuva:.1f} mm/h) — contexto fraco"

    if tipo_norm == "transito":
        indice = valores.get("indice_congestionamento") or valores.get("congestionamento")
        if indice is None:
            return 0.50, "Dados de trânsito sem índice de congestionamento"
        if indice >= 7:
            return 0.92, f"Índice de congestionamento alto ({indice:.1f}/10)"
        if indice >= 4:
            return 0.72, f"Congestionamento moderado ({indice:.1f}/10)"
        return 0.40, f"Índice baixo ({indice:.1f}/10) — contexto fraco para trânsito"

    if tipo_norm == "incendio":
        umidade = valores.get("umidade")
        temp = valores.get("temperatura")
        if umidade is not None and umidade < 40:
            return 0.78, f"Umidade baixa ({umidade:.0f}%) favorece risco de incêndio"
        if temp is not None and temp >= 32:
            return 0.75, f"Temperatura alta ({temp:.0f}°C)"
        if umidade is not None or temp is not None:
            return 0.55, "Condições climáticas neutras para incêndio"
        return 0.48, "Dados climáticos genéricos disponíveis"

    # Demais tipos: presença de qualquer dado climático
    return 0.58, f"Contexto climático genérico para evento tipo '{tipo_norm}'"


def pontuar_clima(tipo: str, dados: list[DadoClima]) -> tuple[float, str]:
    if not dados:
        return 0.30, "Sem dados climáticos vinculados ao evento"
    return _pontuar_clima_por_tipo(tipo, dados)


def pontuar_fonte_oficial(fonte: FonteInfo | None) -> tuple[float, str]:
    if fonte is None:
        return 0.20, "Evento sem fonte de dados identificada"

    tipo = fonte.tipo.lower().strip()

    if tipo in FONTES_OFICIAIS:
        base = 0.92 if tipo == "api" else 0.85 if tipo == "sensor" else 0.88
        if not fonte.ativo:
            base *= 0.85
        nome = fonte.nome or tipo
        return _clamp(base), f"Fonte oficial: {nome} ({tipo})"

    if tipo == "yolo":
        return 0.55, "Apenas detecção IA — aguarda confirmação oficial"

    if tipo == "manual":
        return 0.50, "Registro manual — validação oficial pendente"

    return 0.45, f"Fonte '{tipo}' com credibilidade intermediária"
