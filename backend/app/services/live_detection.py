"""Regras para detectar trânsito parado na imagem de uma câmera da CET-SP.

O YOLO conta quantos veículos aparecem na imagem. Se forem muitos, é trânsito.
Se forem poucos, a TomTom ajuda a decidir se a via está mesmo lenta. Quem chama
estas regras é o ciclo de monitoramento (ciclo_monitoramento.py).
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from app.config import settings
from app.services.detection_events import Analise
from app.services.tomtom_traffic_source import obter_fluxo_transito
from ml.detector import CLASSES_URBANAS, Deteccao, detectar_imagem_real

logger = logging.getLogger(__name__)

_CLASSES_VEICULO = {"veiculo", "motocicleta", "onibus", "caminhao"}
_TRANSITO_ID, _TRANSITO_META = next(
    (classe_id, meta) for classe_id, meta in CLASSES_URBANAS.items() if meta["nome"] == "transito"
)
TIPO = _TRANSITO_META["tipo"]


def _detectar_congestionamento(veiculos: list[Deteccao], limite: int) -> Deteccao:
    """Junta os veículos detectados em um único evento de trânsito.

    A confiança usa só os veículos mais bem detectados, porque os carros ao
    fundo da imagem costumam ter nota baixa.
    """
    melhores = sorted((d.confianca for d in veiculos), reverse=True)[:limite]
    confianca = round(sum(melhores) / len(melhores), 3)
    xs1 = [d.bbox[0] for d in veiculos]
    ys1 = [d.bbox[1] for d in veiculos]
    xs2 = [d.bbox[2] for d in veiculos]
    ys2 = [d.bbox[3] for d in veiculos]
    return Deteccao(
        classe_id=_TRANSITO_ID,
        nome="transito",
        confianca=confianca,
        severidade=_TRANSITO_META["severidade"],
        tipo=_TRANSITO_META["tipo"],
        bbox=(min(xs1), min(ys1), max(xs2), max(ys2)),
    )


def _avaliar_gatilho_transito(n_veiculos: int, fluxo_tomtom: dict) -> tuple[bool, str]:
    """Decide se a quantidade de veículos vira um evento de trânsito.

    Com muitos veículos, cria direto. Com uma quantidade média, cria, a não ser
    que a TomTom diga que a via está fluindo. Com poucos veículos, só cria se a
    TomTom confirmar a lentidão. Devolve a decisão e o motivo.
    """
    if n_veiculos >= settings.gx_transito_min_veiculos_confirmado:
        return True, f"contagem alta ({n_veiculos} veículos)"
    if fluxo_tomtom.get("via_fechada"):
        return True, "TomTom reporta via fechada"

    corroboracao_obrigatoria = n_veiculos < settings.gx_transito_min_veiculos

    indice = fluxo_tomtom.get("indice_congestionamento")
    if not fluxo_tomtom.get("disponivel") or indice is None:
        if corroboracao_obrigatoria:
            return False, f"sem TomTom e contagem baixa ({n_veiculos} veículos), nada a corroborar"
        return True, "sem TomTom, decisão só por contagem"

    if indice >= settings.gx_transito_tomtom_indice_minimo:
        if corroboracao_obrigatoria:
            return True, f"TomTom sustenta a contagem baixa (índice {indice:.1f}/10)"
        return True, f"TomTom confirma lentidão (índice {indice:.1f}/10)"
    return False, f"TomTom indica trecho fluindo (índice {indice:.1f}/10)"


def analisar_frame(conteudo: bytes, latitude: float, longitude: float, nome_camera: str = "câmera personalizada") -> Analise | None:
    """Diz se a imagem mostra trânsito parado.

    Devolve a análise quando há trânsito e None quando não há. Se o modelo não
    estiver disponível, a exceção sobe, porque isso não é o mesmo que não ver
    trânsito e o evento que já existe não pode ser apagado por causa disso.
    """
    caminho = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as arquivo:
            arquivo.write(conteudo)
            caminho = arquivo.name
        deteccoes = detectar_imagem_real(caminho, settings.yolo_threshold)
    finally:
        if caminho:
            Path(caminho).unlink(missing_ok=True)

    veiculos = [item for item in deteccoes if item.nome in _CLASSES_VEICULO]
    # Com tão poucos veículos nem vale consultar a TomTom.
    if len(veiculos) < settings.gx_transito_min_veiculos_corroborado:
        return None

    fluxo_tomtom = obter_fluxo_transito(latitude, longitude)
    criar, motivo = _avaliar_gatilho_transito(len(veiculos), fluxo_tomtom)
    if not criar:
        logger.info("Trânsito descartado em %s: %s (%s veículos no quadro)", nome_camera, motivo, len(veiculos))
        return None

    indice = round(min(10.0, len(veiculos) / 2), 1)
    contexto = [("indice_congestionamento", indice, "indice_0_10")]
    if fluxo_tomtom.get("disponivel") and fluxo_tomtom.get("indice_congestionamento") is not None:
        contexto.append(("indice_congestionamento_tomtom", float(fluxo_tomtom["indice_congestionamento"]), "indice_0_10"))

    logger.info(
        "Trânsito visto em %s: %s veículos no quadro (índice %.1f), %s",
        nome_camera, len(veiculos), indice, motivo,
    )
    return Analise(
        deteccao=_detectar_congestionamento(veiculos, settings.gx_transito_min_veiculos),
        fonte_nome=f"MotSP YOLO Contínuo - {nome_camera}",
        fonte_descricao=f"Contagem de veículos pela câmera pública CET-SP '{nome_camera}', sem confirmação humana.",
        modelo_ia="YOLO11 (contagem de veículos)",
        origem="camera_continua_contagem",
        deteccoes_para_anotar=veiculos,
        contexto=contexto,
    )
