"""Avisos meteorológicos oficiais ativos via INMET (Instituto Nacional de
Meteorologia) — API pública, sem chave, JSON estruturado.

Diferente da leitura de chuva atual (``weather_source.py``, sensor bruto),
isto é o julgamento institucional oficial de que existe risco meteorológico
numa área — mais perto do papel que a dimensão "fonte oficial" do Data
Fusion deveria preencher (hoje sempre 0%, porque a única fonte de todo
evento autônomo é a própria câmera YOLO). Verificado em 26/08/2026
consultando o JSON de verdade, campo por campo (não só a documentação):
havia um aviso ativo real de tempestade cobrindo São Paulo no momento do
teste, com "riscos" mencionando alagamento em texto livre.

A API cobre o Brasil inteiro; aqui filtramos por município via código IBGE
(campo ``geocodes`` — string de códigos separados por vírgula, confirmado no
JSON real) e checamos se o texto livre de "riscos" menciona alagamento.
"""

from __future__ import annotations

import json
from urllib.request import Request, urlopen

_URL = "https://apiprevmet3.inmet.gov.br/avisos/ativos"
_IBGE_SAO_PAULO_CAPITAL = "3550308"
_PALAVRAS_ALAGAMENTO = ("alagamento", "inunda", "enchente")

# Escala de cor oficial do INMET (portal.inmet.gov.br/avisos) — o JSON não
# traz um índice ordinal limpo (id_severidade não é 1/2/3), só o rótulo em
# texto, então a conversão pra índice 0-10 (mesma escala do índice de
# congestionamento do trânsito) é derivada daqui.
_SEVERIDADE_INDICE = {
    "perigo potencial": 4.0,  # amarelo
    "perigo": 7.0,  # laranja
    "grande perigo": 9.5,  # vermelho
}


def _severidade_indice(rotulo: str | None) -> float:
    return _SEVERIDADE_INDICE.get((rotulo or "").lower().strip(), 2.0)


def obter_aviso_ativo(municipio_ibge: str = _IBGE_SAO_PAULO_CAPITAL) -> dict:
    """Aviso ativo mais severo do INMET que cobre o município informado, se houver."""
    request = Request(_URL, headers={"User-Agent": "Mozilla/5.0 (GX-TCC inmet-alert-source)"})
    try:
        with urlopen(request, timeout=8) as response:  # nosec B310 - URL fixa e pública
            payload = json.load(response)
    except Exception as exc:
        return {"disponivel": False, "fonte": "INMET", "erro": str(exc)}

    candidatos = [
        aviso for aviso in (payload.get("hoje") or [])
        if municipio_ibge in (aviso.get("geocodes") or "").split(",")
    ]
    if not candidatos:
        return {"disponivel": False, "fonte": "INMET"}

    mais_severo = max(candidatos, key=lambda aviso: _severidade_indice(aviso.get("severidade")))
    riscos_texto = " ".join(mais_severo.get("riscos") or []).lower()

    return {
        "disponivel": True,
        "fonte": "INMET",
        "descricao": mais_severo.get("descricao"),
        "severidade": mais_severo.get("severidade"),
        "severidade_indice": _severidade_indice(mais_severo.get("severidade")),
        "menciona_alagamento": any(palavra in riscos_texto for palavra in _PALAVRAS_ALAGAMENTO),
        "valido_ate": f"{(mais_severo.get('data_fim') or '')[:10]} {mais_severo.get('hora_fim') or ''}".strip(),
    }
