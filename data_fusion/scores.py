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

    if tipo_norm == "acidente_transito":
        chuva = valores.get("precipitacao_mm_h") or valores.get("precipitacao")
        if chuva is None:
            return 0.45, "Dados climáticos sem precipitação registrada"
        if chuva >= 10:
            return 0.80, f"Chuva forte ({chuva:.1f} mm/h) — pista provavelmente escorregadia"
        if chuva >= 3:
            return 0.65, f"Chuva moderada ({chuva:.1f} mm/h) — aderência reduzida"
        if chuva > 0:
            return 0.55, f"Chuvisco leve ({chuva:.1f} mm/h)"
        return 0.42, "Sem chuva registrada — fator climático fraco para o acidente"

    if tipo_norm == "arvore_caida":
        vento = valores.get("vento_kmh") or valores.get("vento")
        if vento is None:
            return 0.45, "Dados climáticos sem velocidade do vento registrada"
        if vento >= 80:
            return 0.90, f"Vento muito forte ({vento:.0f} km/h) — alto risco de queda"
        if vento >= 60:
            return 0.75, f"Vento forte ({vento:.0f} km/h) — risco elevado de queda"
        if vento >= 40:
            return 0.55, f"Vento moderado ({vento:.0f} km/h) — risco presente"
        return 0.30, f"Vento fraco ({vento:.0f} km/h) — contexto fraco para queda de árvore"

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
