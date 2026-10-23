"""Avisos oficiais do INMET para a cidade de São Paulo.

A API do INMET é pública e cobre o Brasil todo. O sistema filtra os avisos do
município e verifica se o texto deles fala em risco de alagamento.
"""

from __future__ import annotations

import json
from urllib.request import Request, urlopen

_URL = "https://apiprevmet3.inmet.gov.br/avisos/ativos"
_IBGE_SAO_PAULO_CAPITAL = "3550308"
_PALAVRAS_ALAGAMENTO = ("alagamento", "inunda", "enchente")

# O INMET só informa o nível do aviso em texto. Aqui cada nível vira um número
# de 0 a 10, a mesma escala usada no trânsito.
_SEVERIDADE_INDICE = {
    "perigo potencial": 4.0,  # amarelo
    "perigo": 7.0,  # laranja
    "grande perigo": 9.5,  # vermelho
}


def _severidade_indice(rotulo: str | None) -> float:
    return _SEVERIDADE_INDICE.get((rotulo or "").lower().strip(), 2.0)


def obter_aviso_ativo(municipio_ibge: str = _IBGE_SAO_PAULO_CAPITAL) -> dict:
    """Devolve o aviso mais grave do INMET para o município, se houver."""
    request = Request(_URL, headers={"User-Agent": "Mozilla/5.0 (MotSP inmet-alert-source)"})
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
